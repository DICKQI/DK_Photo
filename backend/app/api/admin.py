from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import or_
from sqlmodel import select

from app.config import settings
from app.deps import AdminUser, SessionDep
from app.models import (
    Asset,
    AssetFavorite,
    AssetMetadata,
    AssetTag,
    Folder,
    LibraryPermission,
    LibraryRoot,
    PhotoAlbum,
    PhotoAlbumAsset,
    ScanJob,
    ShareAsset,
    ShareLink,
    Thumbnail,
    User,
)
from app.schemas import (
    FilesystemChildren,
    FilesystemRoots,
    LibraryCreate,
    LibraryPermissionRead,
    LibraryPermissionUpdate,
    LibraryRead,
    LibraryUpdate,
    PasswordReset,
    ScanJobRead,
    ShareRead,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.security import hash_password
from app.api.shares import share_read
from app.services.filesystem import list_children, list_roots
from app.services.paths import resolve_library_path
from app.services.scanner import run_scan_job


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/libraries", response_model=list[LibraryRead])
def list_libraries(session: SessionDep, _: AdminUser) -> list[LibraryRoot]:
    return session.exec(select(LibraryRoot).order_by(LibraryRoot.name)).all()


@router.get("/filesystem/roots", response_model=FilesystemRoots)
def filesystem_roots(_: AdminUser) -> FilesystemRoots:
    return list_roots()


@router.get("/filesystem/children", response_model=FilesystemChildren)
def filesystem_children(path: str, _: AdminUser) -> FilesystemChildren:
    return list_children(path)


@router.post("/libraries", response_model=LibraryRead)
def create_library(payload: LibraryCreate, request: Request, session: SessionDep, _: AdminUser) -> LibraryRoot:
    path = resolve_library_path(payload.path)
    existing = session.exec(select(LibraryRoot).where(LibraryRoot.path == str(path))).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Library already exists")
    library = LibraryRoot(name=payload.name, path=str(path), is_enabled=True)
    session.add(library)
    session.commit()
    session.refresh(library)
    watcher = getattr(request.app.state, "library_watcher", None)
    if watcher:
        watcher.refresh()
    return library


@router.patch("/libraries/{library_id}", response_model=LibraryRead)
def update_library(library_id: int, payload: LibraryUpdate, session: SessionDep, _: AdminUser) -> LibraryRoot:
    library = session.get(LibraryRoot, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Library name is required")
        library.name = name
        root_folder = session.exec(
            select(Folder).where(Folder.library_id == library_id, Folder.parent_id == None)
        ).first()
        if root_folder:
            root_folder.name = name
    session.commit()
    session.refresh(library)
    return library


@router.delete("/libraries/{library_id}")
def delete_library(library_id: int, request: Request, session: SessionDep, _: AdminUser) -> dict[str, bool]:
    library = session.get(LibraryRoot, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")

    assets = session.exec(select(Asset).where(Asset.library_id == library_id)).all()
    folders = session.exec(select(Folder).where(Folder.library_id == library_id)).all()
    asset_ids = [asset.id for asset in assets if asset.id is not None]
    folder_ids = [folder.id for folder in folders if folder.id is not None]

    if asset_ids or folder_ids:
        share_conditions = []
        if asset_ids:
            share_conditions.append(ShareLink.asset_id.in_(asset_ids))  # type: ignore[attr-defined]
        if folder_ids:
            share_conditions.append(ShareLink.folder_id.in_(folder_ids))  # type: ignore[attr-defined]
        shares = session.exec(select(ShareLink).where(or_(*share_conditions))).all()
        for share in shares:
            session.delete(share)

    if asset_ids:
        favorites = session.exec(select(AssetFavorite).where(AssetFavorite.asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
        for favorite in favorites:
            session.delete(favorite)
        tags = session.exec(select(AssetTag).where(AssetTag.asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
        for tag in tags:
            session.delete(tag)
        metadata_rows = session.exec(select(AssetMetadata).where(AssetMetadata.asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
        for metadata in metadata_rows:
            session.delete(metadata)

        album_assets = session.exec(select(PhotoAlbumAsset).where(PhotoAlbumAsset.asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
        for album_asset in album_assets:
            session.delete(album_asset)
        cover_albums = session.exec(select(PhotoAlbum).where(PhotoAlbum.cover_asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
        for album in cover_albums:
            album.cover_asset_id = None

        multi_share_assets = session.exec(select(ShareAsset).where(ShareAsset.asset_id.in_(asset_ids))).all()
        affected_share_ids = {sa.share_id for sa in multi_share_assets}
        for sa in multi_share_assets:
            session.delete(sa)
        session.flush()
        for sid in affected_share_ids:
            remaining = session.exec(select(ShareAsset).where(ShareAsset.share_id == sid)).all()
            if not remaining:
                share = session.get(ShareLink, sid)
                if share:
                    session.delete(share)

    if asset_ids:
        thumbnails = session.exec(select(Thumbnail).where(Thumbnail.asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
        for thumbnail in thumbnails:
            _unlink_thumbnail_file(thumbnail.path)
            session.delete(thumbnail)

    for folder in folders:
        folder.cover_asset_id = None
        folder.parent_id = None
    session.flush()

    for permission in session.exec(select(LibraryPermission).where(LibraryPermission.library_id == library_id)).all():
        session.delete(permission)
    for job in session.exec(select(ScanJob).where(ScanJob.library_id == library_id)).all():
        session.delete(job)
    for asset in assets:
        session.delete(asset)
    for folder in folders:
        session.delete(folder)
    session.delete(library)
    session.commit()

    watcher = getattr(request.app.state, "library_watcher", None)
    if watcher:
        watcher.refresh()
    return {"ok": True}


def _unlink_thumbnail_file(path: str) -> None:
    try:
        thumbnail_path = Path(path).resolve()
        thumbnail_path.relative_to(settings.thumbnail_dir.resolve())
    except (OSError, ValueError):
        return
    try:
        thumbnail_path.unlink(missing_ok=True)
    except OSError:
        return


@router.post("/libraries/{library_id}/scan", response_model=ScanJobRead)
def scan_library_endpoint(
    library_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    _: AdminUser,
) -> ScanJob:
    library = session.get(LibraryRoot, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    if not Path(library.path).exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Library path does not exist")
    job = ScanJob(library_id=library_id, status="queued", message="Manual scan queued")
    session.add(job)
    session.commit()
    session.refresh(job)
    background_tasks.add_task(_run_job_in_new_session, job.id or 0)
    return job


def _run_job_in_new_session(job_id: int) -> None:
    from sqlmodel import Session

    from app.db import engine

    with Session(engine) as session:
        run_scan_job(session, job_id)


@router.get("/jobs", response_model=list[ScanJobRead])
def list_jobs(session: SessionDep, _: AdminUser) -> list[ScanJob]:
    return session.exec(select(ScanJob).order_by(ScanJob.id.desc()).limit(40)).all()


@router.get("/users", response_model=list[UserRead])
def list_users(session: SessionDep, _: AdminUser) -> list[User]:
    return session.exec(select(User).order_by(User.created_at.desc())).all()


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: SessionDep, _: AdminUser) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/users", response_model=UserRead)
def create_user(payload: UserCreate, session: SessionDep, _: AdminUser) -> User:
    role = payload.role if payload.role in {"admin", "member"} else "member"
    existing = session.exec(select(User).where(User.email == payload.email.lower())).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name,
        role=role,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, session: SessionDep, _: AdminUser) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.email and payload.email.lower() != user.email:
        existing = session.exec(select(User).where(User.email == payload.email.lower(), User.id != user_id)).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        user.email = payload.email.lower()
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role if payload.role in {"admin", "member"} else user.role
    session.commit()
    session.refresh(user)
    return user


@router.post("/users/{user_id}/password")
def reset_user_password(user_id: int, payload: PasswordReset, session: SessionDep, _: AdminUser) -> dict[str, bool]:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.password_hash = hash_password(payload.password)
    session.commit()
    return {"ok": True}


@router.post("/users/{user_id}/disable", response_model=UserRead)
def disable_user(user_id: int, session: SessionDep, admin: AdminUser) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot disable your own account")
    user.is_active = False
    session.commit()
    session.refresh(user)
    return user


@router.post("/users/{user_id}/enable", response_model=UserRead)
def enable_user(user_id: int, session: SessionDep, _: AdminUser) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = True
    session.commit()
    session.refresh(user)
    return user


@router.get("/users/{user_id}/permissions", response_model=list[LibraryPermissionRead])
def get_user_permissions(user_id: int, session: SessionDep, _: AdminUser) -> list[LibraryPermission]:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return session.exec(select(LibraryPermission).where(LibraryPermission.user_id == user_id)).all()


@router.put("/users/{user_id}/permissions", response_model=list[LibraryPermissionRead])
def update_user_permissions(
    user_id: int,
    payload: list[LibraryPermissionUpdate],
    session: SessionDep,
    _: AdminUser,
) -> list[LibraryPermission]:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    existing = session.exec(select(LibraryPermission).where(LibraryPermission.user_id == user_id)).all()
    by_library = {item.library_id: item for item in existing}
    seen_library_ids: set[int] = set()

    for item in payload:
        library = session.get(LibraryRoot, item.library_id)
        if not library:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Library {item.library_id} not found")
        seen_library_ids.add(item.library_id)
        permission = by_library.get(item.library_id)
        if item.can_view:
            if permission:
                permission.can_view = True
                permission.can_share = item.can_share
            else:
                session.add(
                    LibraryPermission(
                        user_id=user_id,
                        library_id=item.library_id,
                        can_view=True,
                        can_share=item.can_share,
                    )
                )
        elif permission:
            session.delete(permission)

    for permission in existing:
        if permission.library_id not in seen_library_ids:
            session.delete(permission)

    session.commit()
    return session.exec(select(LibraryPermission).where(LibraryPermission.user_id == user_id)).all()


@router.get("/shares", response_model=list[ShareRead])
def list_shares(session: SessionDep, _: AdminUser) -> list[ShareRead]:
    shares = session.exec(select(ShareLink).order_by(ShareLink.created_at.desc())).all()
    return [share_read(session, share) for share in shares]


@router.post("/maintenance/cleanup-thumbnails")
def cleanup_thumbnails(session: SessionDep, _: AdminUser) -> dict:
    db_paths = set(
        session.exec(select(Thumbnail.path)).all()
    )
    thumbnail_root = settings.thumbnail_dir
    if not thumbnail_root.exists():
        return {"deleted_files": 0, "freed_bytes": 0, "deleted_dirs": 0}

    deleted_files = 0
    freed_bytes = 0
    all_dirs: set[Path] = set()

    for path in thumbnail_root.rglob("*.webp"):
        all_dirs.add(path.parent)
        if str(path) not in db_paths:
            freed_bytes += path.stat().st_size
            path.unlink()
            deleted_files += 1

    deleted_dirs = 0
    for directory in sorted(all_dirs, key=lambda p: len(p.parents), reverse=True):
        try:
            if not any(directory.iterdir()):
                directory.rmdir()
                deleted_dirs += 1
        except OSError:
            pass

    return {"deleted_files": deleted_files, "freed_bytes": freed_bytes, "deleted_dirs": deleted_dirs}
