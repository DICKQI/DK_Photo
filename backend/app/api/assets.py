from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlmodel import select

from app.deps import CurrentUser, SessionDep
from app.models import Asset, LibraryRoot
from app.schemas import AssetRead
from app.services.paths import safe_asset_path
from app.services.permissions import accessible_library_ids, require_asset_access
from app.services.thumbnails import ensure_thumbnail


router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=list[AssetRead])
def list_assets(
    session: SessionDep,
    current_user: CurrentUser,
    folder_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
) -> list[Asset]:
    statement = select(Asset)
    if folder_id is not None:
        statement = statement.where(Asset.folder_id == folder_id)
    if search:
        statement = statement.where(Asset.filename.contains(search))
    allowed_library_ids = accessible_library_ids(session, current_user)
    if allowed_library_ids is not None:
        if not allowed_library_ids:
            return []
        statement = statement.where(Asset.library_id.in_(allowed_library_ids))
    statement = statement.order_by(Asset.filename)
    return session.exec(statement).all()


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(asset_id: int, session: SessionDep, current_user: CurrentUser) -> Asset:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    return asset


@router.get("/{asset_id}/original")
def get_original(asset_id: int, session: SessionDep, current_user: CurrentUser) -> FileResponse:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    library = session.get(LibraryRoot, asset.library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    original = safe_asset_path(library.path, asset.path)
    return FileResponse(original, media_type=asset.mime_type, filename=asset.filename)


@router.get("/{asset_id}/thumbnail")
def get_thumbnail(
    asset_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    size: str = Query(default="medium", pattern="^(small|medium|large)$"),
) -> FileResponse:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    thumbnail = ensure_thumbnail(session, asset, size)
    return FileResponse(thumbnail, media_type="image/webp")
