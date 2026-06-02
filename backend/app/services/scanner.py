from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Asset, Folder, LibraryRoot, ScanJob, Thumbnail, utc_now


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def relative_posix(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    return "" if str(relative) == "." else relative.as_posix()


def get_image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            return image.size
    except (OSError, UnidentifiedImageError):
        return None, None


def get_or_create_folder(
    session: Session,
    library: LibraryRoot,
    directory: Path,
    root: Path,
    cache: dict[str, Folder],
) -> Folder:
    rel_path = relative_posix(directory, root)
    if rel_path in cache:
        return cache[rel_path]

    parent_id = None
    if rel_path:
        parent = get_or_create_folder(session, library, directory.parent, root, cache)
        parent_id = parent.id

    folder = session.exec(select(Folder).where(Folder.library_id == library.id, Folder.path == rel_path)).first()
    name = library.name if rel_path == "" else directory.name
    if folder:
        folder.name = name
        folder.parent_id = parent_id
        folder.updated_at = utc_now()
    else:
        folder = Folder(library_id=library.id or 0, parent_id=parent_id, path=rel_path, name=name)
        session.add(folder)
        session.commit()
        session.refresh(folder)
    cache[rel_path] = folder
    return folder


def upsert_asset(session: Session, library: LibraryRoot, folder: Folder, image_path: Path, root: Path) -> Asset:
    rel_path = relative_posix(image_path, root)
    stat = image_path.stat()
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    asset = session.exec(select(Asset).where(Asset.library_id == library.id, Asset.path == rel_path)).first()
    needs_metadata = not asset or asset.size != stat.st_size or asset.mtime != stat.st_mtime
    width = asset.width if asset else None
    height = asset.height if asset else None
    if needs_metadata:
        width, height = get_image_size(image_path)

    if asset:
        asset.folder_id = folder.id or 0
        asset.filename = image_path.name
        asset.mime_type = mime_type
        asset.size = stat.st_size
        asset.mtime = stat.st_mtime
        asset.width = width
        asset.height = height
        asset.updated_at = utc_now()
    else:
        asset = Asset(
            library_id=library.id or 0,
            folder_id=folder.id or 0,
            filename=image_path.name,
            path=rel_path,
            mime_type=mime_type,
            width=width,
            height=height,
            size=stat.st_size,
            mtime=stat.st_mtime,
        )
        session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def delete_missing_assets(session: Session, library: LibraryRoot, seen_asset_paths: set[str]) -> None:
    assets = session.exec(select(Asset).where(Asset.library_id == library.id)).all()
    for asset in assets:
        if asset.path in seen_asset_paths:
            continue
        thumbnails = session.exec(select(Thumbnail).where(Thumbnail.asset_id == asset.id)).all()
        for thumbnail in thumbnails:
            thumb_path = Path(thumbnail.path)
            if thumb_path.exists():
                thumb_path.unlink(missing_ok=True)
            session.delete(thumbnail)
        session.delete(asset)
    session.commit()


def delete_missing_folders(session: Session, library: LibraryRoot, seen_folder_paths: set[str]) -> None:
    folders = session.exec(select(Folder).where(Folder.library_id == library.id)).all()
    folders.sort(key=lambda folder: folder.path.count("/"), reverse=True)
    for folder in folders:
        if folder.path not in seen_folder_paths:
            session.delete(folder)
    session.commit()


def refresh_folder_counts(session: Session, library: LibraryRoot) -> None:
    folders = session.exec(select(Folder).where(Folder.library_id == library.id)).all()
    for folder in folders:
        folder.photo_count = session.exec(
            select(func.count()).select_from(Asset).where(Asset.folder_id == folder.id)
        ).one()
        folder.folder_count = session.exec(
            select(func.count()).select_from(Folder).where(Folder.parent_id == folder.id)
        ).one()
        cover = session.exec(select(Asset).where(Asset.folder_id == folder.id).order_by(Asset.mtime.desc())).first()
        folder.cover_asset_id = cover.id if cover else folder.cover_asset_id
        folder.updated_at = utc_now()
    session.commit()


def scan_library(session: Session, library_id: int) -> int:
    library = session.get(LibraryRoot, library_id)
    if not library or not library.is_enabled:
        return 0
    root = Path(library.path).resolve()
    if not root.exists() or not root.is_dir():
        return 0

    folder_cache: dict[str, Folder] = {}
    seen_folder_paths: set[str] = set()
    seen_asset_paths: set[str] = set()
    total = 0

    for directory, subdirs, filenames in root.walk():
        subdirs[:] = [name for name in subdirs if not name.startswith(".")]
        folder = get_or_create_folder(session, library, directory, root, folder_cache)
        seen_folder_paths.add(folder.path)
        for filename in filenames:
            image_path = directory / filename
            if not is_supported_image(image_path):
                continue
            asset = upsert_asset(session, library, folder, image_path, root)
            seen_asset_paths.add(asset.path)
            total += 1

    delete_missing_assets(session, library, seen_asset_paths)
    delete_missing_folders(session, library, seen_folder_paths)
    refresh_folder_counts(session, library)
    library.last_scan_at = utc_now()
    session.commit()
    return total


def run_scan_job(session: Session, job_id: int) -> None:
    job = session.get(ScanJob, job_id)
    if not job:
        return
    job.status = "running"
    job.started_at = datetime.utcnow()
    session.commit()
    try:
        total = scan_library(session, job.library_id)
    except Exception as exc:  # pragma: no cover - defensive status reporting
        job.status = "failed"
        job.message = str(exc)
        job.finished_at = datetime.utcnow()
        session.commit()
        raise
    job.status = "completed"
    job.total_assets = total
    job.message = f"Indexed {total} photos"
    job.finished_at = datetime.utcnow()
    session.commit()
