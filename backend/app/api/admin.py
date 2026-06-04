from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import or_
from sqlmodel import Session, select

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
    utc_now,
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
    ShareUpdate,
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
        run_scan_job(session, job_id, generate_thumbnails=True)


@router.get("/jobs", response_model=list[ScanJobRead])
def list_jobs(session: SessionDep, _: AdminUser) -> list[ScanJob]:
    return session.exec(select(ScanJob).order_by(ScanJob.id.desc()).limit(40)).all()


def managed_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user or user.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def revoke_user_shares(session: Session, user_id: int) -> None:
    now = utc_now()
    shares = session.exec(
        select(ShareLink).where(ShareLink.creator_id == user_id, ShareLink.revoked_at == None)
    ).all()
    for share in shares:
        share.revoked_at = now
        session.add(share)


def revoke_user_shares_outside_libraries(session: Session, user_id: int, allowed_library_ids: set[int]) -> None:
    now = utc_now()
    shares = session.exec(
        select(ShareLink).where(ShareLink.creator_id == user_id, ShareLink.revoked_at == None)
    ).all()
    for share in shares:
        library_ids = share_library_ids(session, share)
        if not library_ids or not library_ids.issubset(allowed_library_ids):
            share.revoked_at = now
            session.add(share)


def share_library_ids(session: Session, share: ShareLink) -> set[int]:
    if share.asset_id:
        asset = session.get(Asset, share.asset_id)
        return {asset.library_id} if asset else set()
    if share.folder_id:
        folder = session.get(Folder, share.folder_id)
        return {folder.library_id} if folder else set()
    assets = session.exec(
        select(Asset)
        .join(ShareAsset, ShareAsset.asset_id == Asset.id)
        .where(ShareAsset.share_id == share.id)
    ).all()
    return {asset.library_id for asset in assets}


def delete_user_personal_data(session: Session, user_id: int) -> None:
    for permission in session.exec(select(LibraryPermission).where(LibraryPermission.user_id == user_id)).all():
        session.delete(permission)
    for favorite in session.exec(select(AssetFavorite).where(AssetFavorite.user_id == user_id)).all():
        session.delete(favorite)
    for tag in session.exec(select(AssetTag).where(AssetTag.user_id == user_id)).all():
        session.delete(tag)
    for metadata in session.exec(select(AssetMetadata).where(AssetMetadata.user_id == user_id)).all():
        session.delete(metadata)
    albums = session.exec(select(PhotoAlbum).where(PhotoAlbum.owner_id == user_id)).all()
    album_ids = [album.id for album in albums if album.id is not None]
    if album_ids:
        album_assets = session.exec(select(PhotoAlbumAsset).where(PhotoAlbumAsset.album_id.in_(album_ids))).all()  # type: ignore[attr-defined]
        for album_asset in album_assets:
            session.delete(album_asset)
    for album in albums:
        session.delete(album)


@router.get("/users", response_model=list[UserRead])
def list_users(session: SessionDep, _: AdminUser) -> list[User]:
    return session.exec(
        select(User).where(User.deleted_at == None).order_by(User.created_at.desc())
    ).all()


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: SessionDep, _: AdminUser) -> User:
    return managed_user(session, user_id)


@router.post("/users", response_model=UserRead)
def create_user(payload: UserCreate, session: SessionDep, _: AdminUser) -> User:
    role = payload.role if payload.role in {"admin", "member"} else "member"
    existing = session.exec(
        select(User).where(User.email == payload.email.lower(), User.deleted_at == None)
    ).first()
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
    user = managed_user(session, user_id)
    if payload.email and payload.email.lower() != user.email:
        existing = session.exec(
            select(User).where(
                User.email == payload.email.lower(),
                User.id != user_id,
                User.deleted_at == None,
            )
        ).first()
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
    user = managed_user(session, user_id)
    user.password_hash = hash_password(payload.password)
    user.token_version += 1
    session.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, session: SessionDep, admin: AdminUser) -> dict[str, bool]:
    user = managed_user(session, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account")

    revoke_user_shares(session, user_id)
    delete_user_personal_data(session, user_id)
    now = utc_now()
    user.is_active = False
    user.role = "member"
    user.token_version += 1
    user.deleted_at = now
    user.email = f"deleted-user-{user.id}-{int(now.timestamp())}@deleted.local"
    user.display_name = "Deleted User"
    session.add(user)
    session.commit()
    return {"ok": True}


@router.post("/users/{user_id}/disable", response_model=UserRead)
def disable_user(user_id: int, session: SessionDep, admin: AdminUser) -> User:
    user = managed_user(session, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot disable your own account")
    user.is_active = False
    user.token_version += 1
    revoke_user_shares(session, user_id)
    session.commit()
    session.refresh(user)
    return user


@router.post("/users/{user_id}/enable", response_model=UserRead)
def enable_user(user_id: int, session: SessionDep, _: AdminUser) -> User:
    user = managed_user(session, user_id)
    user.is_active = True
    session.commit()
    session.refresh(user)
    return user


@router.get("/users/{user_id}/permissions", response_model=list[LibraryPermissionRead])
def get_user_permissions(user_id: int, session: SessionDep, _: AdminUser) -> list[LibraryPermission]:
    managed_user(session, user_id)
    return session.exec(select(LibraryPermission).where(LibraryPermission.user_id == user_id)).all()


@router.put("/users/{user_id}/permissions", response_model=list[LibraryPermissionRead])
def update_user_permissions(
    user_id: int,
    payload: list[LibraryPermissionUpdate],
    session: SessionDep,
    _: AdminUser,
) -> list[LibraryPermission]:
    user = managed_user(session, user_id)
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

    if user.role != "admin":
        allowed_share_library_ids = {
            item.library_id for item in payload if item.can_view and item.can_share
        }
        revoke_user_shares_outside_libraries(session, user_id, allowed_share_library_ids)

    session.commit()
    return session.exec(select(LibraryPermission).where(LibraryPermission.user_id == user_id)).all()


@router.get("/shares", response_model=list[ShareRead])
def list_shares(session: SessionDep, _: AdminUser) -> list[ShareRead]:
    shares = session.exec(select(ShareLink).order_by(ShareLink.created_at.desc())).all()
    return [share_read(session, share) for share in shares]


@router.patch("/shares/{share_id}", response_model=ShareRead)
def update_any_share(share_id: int, payload: ShareUpdate, session: SessionDep, _: AdminUser) -> ShareRead:
    share = session.get(ShareLink, share_id)
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if share.revoked_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Share is already revoked")
    if payload.title is not None:
        share.title = payload.title
    if payload.expires_in_days is not None:
        if payload.expires_in_days > 0:
            share.expires_at = utc_now() + timedelta(days=payload.expires_in_days)
        else:
            share.expires_at = None
    if payload.password is not None:
        if payload.password:
            share.password_hash = hash_password(payload.password)
        else:
            share.password_hash = None
    session.add(share)
    session.commit()
    session.refresh(share)
    return share_read(session, share)


@router.delete("/shares/{share_id}")
def revoke_any_share(share_id: int, session: SessionDep, _: AdminUser) -> dict[str, bool]:
    share = session.get(ShareLink, share_id)
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if share.revoked_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Share is already revoked")
    share.revoked_at = utc_now()
    session.add(share)
    session.commit()
    return {"ok": True}


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
