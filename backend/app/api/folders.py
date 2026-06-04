from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from app.deps import AdminUser, CurrentUser, SessionDep
from app.models import Asset, Folder
from app.schemas import FolderCoverUpdate, FolderDetail, FolderRead, FolderRenameUpdate
from app.services.permissions import accessible_library_ids, require_folder_access


router = APIRouter(prefix="/api/folders", tags=["folders"])


@router.get("", response_model=list[FolderRead])
def list_folders(
    session: SessionDep,
    current_user: CurrentUser,
    parent_id: int | None = Query(default=None),
    library_id: int | None = Query(default=None),
) -> list[Folder]:
    statement = select(Folder).where(Folder.parent_id == parent_id).order_by(Folder.name)
    if library_id is not None:
        statement = statement.where(Folder.library_id == library_id)
    allowed_library_ids = accessible_library_ids(session, current_user)
    if allowed_library_ids is not None:
        if not allowed_library_ids:
            return []
        statement = statement.where(Folder.library_id.in_(allowed_library_ids))
    return session.exec(statement).all()


@router.get("/{folder_id}", response_model=FolderDetail)
def get_folder(folder_id: int, session: SessionDep, current_user: CurrentUser) -> FolderDetail:
    folder = session.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    require_folder_access(session, current_user, folder)
    ancestors: list[Folder] = []
    current = folder
    while current.parent_id:
        parent = session.get(Folder, current.parent_id)
        if not parent:
            break
        ancestors.append(parent)
        current = parent
    ancestors.reverse()
    data = FolderDetail.model_validate(folder, from_attributes=True)
    data.ancestors = [FolderRead.model_validate(item, from_attributes=True) for item in ancestors]
    return data


@router.patch("/{folder_id}/cover", response_model=FolderRead)
def update_folder_cover(folder_id: int, payload: FolderCoverUpdate, session: SessionDep, _: AdminUser) -> Folder:
    folder = session.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    asset = session.get(Asset, payload.cover_asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    if asset.folder_id != folder.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset does not belong to this folder")
    folder.cover_asset_id = asset.id
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return folder


@router.patch("/{folder_id}/rename", response_model=FolderRead)
def rename_folder(folder_id: int, payload: FolderRenameUpdate, session: SessionDep, _: AdminUser) -> Folder:
    folder = session.get(Folder, folder_id)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Folder name is required")
    folder.name = name
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return folder
