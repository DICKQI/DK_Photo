from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.config import get_thumb_workers, reset_thumb_workers, set_thumb_workers, settings
from app.deps import AdminUser, CurrentUser, SessionDep
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
    ServerSettingsRead,
    ServerSettingsUpdate,
    ShareRead,
    ShareUpdate,
    ThumbnailStats,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.security import hash_password
from app.api.shares import share_read
from app.services.filesystem import list_children, list_roots
from app.services.paths import is_docker_photos_root, resolve_library_path
from app.services.scanner import active_scan_job, request_cancel_scan_job, run_scan_job


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
    library = LibraryRoot(name=payload.name, path=str(path), is_enabled=True, watch_enabled=payload.watch_enabled)
    session.add(library)
    session.commit()
    session.refresh(library)
    watcher = getattr(request.app.state, "library_watcher", None)
    if watcher:
        watcher.refresh()
    return library


@router.patch("/libraries/{library_id}", response_model=LibraryRead)
def update_library(library_id: int, payload: LibraryUpdate, request: Request, session: SessionDep, _: AdminUser) -> LibraryRoot:
    library = session.get(LibraryRoot, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    if library.deleted_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Library is being deleted")
    watch_changed = False
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
    if payload.watch_enabled is not None and payload.watch_enabled != library.watch_enabled:
        library.watch_enabled = payload.watch_enabled
        watch_changed = True
    session.commit()
    session.refresh(library)
    if watch_changed:
        watcher = getattr(request.app.state, "library_watcher", None)
        if watcher:
            watcher.refresh()
    return library


@router.delete("/libraries/{library_id}")
def delete_library(
    library_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    _: AdminUser,
) -> dict[str, bool]:
    library = session.get(LibraryRoot, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    if library.deleted_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Library is already being deleted")

    active_job = active_scan_job(session, library_id)
    if active_job:
        request_cancel_scan_job(active_job.id or 0)

    library.is_enabled = False
    library.deleted_at = utc_now()
    session.commit()

    watcher = getattr(request.app.state, "library_watcher", None)
    if watcher:
        watcher.refresh()

    background_tasks.add_task(_delete_library_cleanup, library_id)
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


def _delete_library_cleanup(library_id: int) -> None:
    from sqlmodel import Session

    from app.db import engine

    with Session(engine) as cleanup_session:
        assets = cleanup_session.exec(select(Asset).where(Asset.library_id == library_id)).all()
        folders = cleanup_session.exec(select(Folder).where(Folder.library_id == library_id)).all()
        asset_ids = [a.id for a in assets if a.id is not None]
        folder_ids = [f.id for f in folders if f.id is not None]

        if asset_ids or folder_ids:
            share_conditions = []
            if asset_ids:
                share_conditions.append(ShareLink.asset_id.in_(asset_ids))  # type: ignore[attr-defined]
            if folder_ids:
                share_conditions.append(ShareLink.folder_id.in_(folder_ids))  # type: ignore[attr-defined]
            shares = cleanup_session.exec(select(ShareLink).where(or_(*share_conditions))).all()
            for share in shares:
                cleanup_session.delete(share)

        if asset_ids:
            for model in (AssetFavorite, AssetTag, AssetMetadata):
                rows = cleanup_session.exec(select(model).where(model.asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
                for row in rows:
                    cleanup_session.delete(row)

            album_assets = cleanup_session.exec(select(PhotoAlbumAsset).where(PhotoAlbumAsset.asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
            for aa in album_assets:
                cleanup_session.delete(aa)
            cover_albums = cleanup_session.exec(select(PhotoAlbum).where(PhotoAlbum.cover_asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
            for album in cover_albums:
                album.cover_asset_id = None

            multi_share_assets = cleanup_session.exec(select(ShareAsset).where(ShareAsset.asset_id.in_(asset_ids))).all()
            affected_share_ids = {sa.share_id for sa in multi_share_assets}
            for sa in multi_share_assets:
                cleanup_session.delete(sa)
            cleanup_session.flush()
            for sid in affected_share_ids:
                if not cleanup_session.exec(select(ShareAsset).where(ShareAsset.share_id == sid)).all():
                    share = cleanup_session.get(ShareLink, sid)
                    if share:
                        cleanup_session.delete(share)

        if asset_ids:
            thumbnails = cleanup_session.exec(select(Thumbnail).where(Thumbnail.asset_id.in_(asset_ids))).all()  # type: ignore[attr-defined]
            for thumb in thumbnails:
                _unlink_thumbnail_file(thumb.path)
                cleanup_session.delete(thumb)

        for folder in folders:
            folder.cover_asset_id = None
            folder.parent_id = None
        cleanup_session.flush()

        for perm in cleanup_session.exec(select(LibraryPermission).where(LibraryPermission.library_id == library_id)).all():
            cleanup_session.delete(perm)
        for job in cleanup_session.exec(select(ScanJob).where(ScanJob.library_id == library_id)).all():
            cleanup_session.delete(job)
        for asset in assets:
            cleanup_session.delete(asset)
        for folder in folders:
            cleanup_session.delete(folder)

        library = cleanup_session.get(LibraryRoot, library_id)
        if library:
            cleanup_session.delete(library)
        cleanup_session.commit()


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
    if not library.is_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Library is disabled")
    if is_docker_photos_root(library.path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="/photos is only the Docker mount root. Choose a mounted subdirectory such as /photos/travel.",
        )
    try:
        path_exists = Path(library.path).exists()
    except OSError:
        path_exists = False
    if not path_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Library path does not exist")
    existing_job = active_scan_job(session, library_id)
    if existing_job:
        return existing_job
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


@router.get("/jobs/active", response_model=list[ScanJobRead])
def list_active_jobs(session: SessionDep, _: CurrentUser) -> list[ScanJobRead]:
    """Return only queued/running scan jobs. Accessible to all authenticated users."""
    rows = session.exec(
        select(ScanJob, LibraryRoot.name)
        .join(LibraryRoot, ScanJob.library_id == LibraryRoot.id, isouter=True)
        .where(ScanJob.status.in_(("queued", "running")))
        .order_by(ScanJob.id.desc())
    ).all()
    result: list[ScanJobRead] = []
    for job, lib_name in rows:
        result.append(ScanJobRead(
            id=job.id or 0,
            library_id=job.library_id,
            status=job.status,
            message=job.message,
            total_assets=job.total_assets,
            total_estimated=job.total_estimated,
            processed_assets=job.processed_assets,
            started_at=job.started_at,
            finished_at=job.finished_at,
            library_name=lib_name or f"Library {job.library_id}",
        ))
    return result


@router.post("/jobs/{job_id}/cancel")
def cancel_scan_job(job_id: int, session: SessionDep, _: AdminUser) -> dict:
    job = session.get(ScanJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan job not found")
    if job.status not in ("queued", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel scan job with status '{job.status}'",
        )

    if job.status == "queued":
        request_cancel_scan_job(job_id)
        job.status = "cancelled"
        job.message = "Scan cancelled before start"
        job.finished_at = datetime.utcnow()
        session.commit()
        return {"ok": True}

    ok = request_cancel_scan_job(job_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not cancel the running scan (job may be in a different process)",
        )
    return {"ok": True}


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
        if library.deleted_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Library {item.library_id} is being deleted")
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


@router.get("/thumbnail-stats", response_model=ThumbnailStats)
def get_thumbnail_stats(session: SessionDep, _: AdminUser) -> ThumbnailStats:
    counts = session.exec(
        select(Thumbnail.size, func.count(Thumbnail.id)).group_by(Thumbnail.size)  # type: ignore[attr-defined]
    ).all()
    count_map = {size: cnt for size, cnt in counts}

    total_size_bytes = 0
    thumbnail_root = settings.thumbnail_dir
    if thumbnail_root.exists():
        for path in thumbnail_root.rglob("*.webp"):
            try:
                total_size_bytes += path.stat().st_size
            except OSError:
                pass

    return ThumbnailStats(
        total_count=sum(count_map.values()),
        total_size_bytes=total_size_bytes,
        small_count=count_map.get("small", 0),
        medium_count=count_map.get("medium", 0),
        large_count=count_map.get("large", 0),
    )


@router.get("/settings", response_model=ServerSettingsRead)
def get_settings(_: AdminUser) -> ServerSettingsRead:
    import os

    return ServerSettingsRead(
        thumb_workers=get_thumb_workers(),
        cpu_count=os.cpu_count(),
        thumb_workers_default=settings.thumb_workers,
    )


@router.put("/settings", response_model=ServerSettingsRead)
def update_settings(payload: ServerSettingsUpdate, _: AdminUser) -> ServerSettingsRead:
    import os

    set_thumb_workers(payload.thumb_workers)
    return ServerSettingsRead(
        thumb_workers=get_thumb_workers(),
        cpu_count=os.cpu_count(),
        thumb_workers_default=settings.thumb_workers,
    )


@router.delete("/settings/thumb-workers-reset")
def reset_thumb_workers_endpoint(_: AdminUser) -> dict[str, bool]:
    reset_thumb_workers()
    return {"ok": True}
