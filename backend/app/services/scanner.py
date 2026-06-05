from __future__ import annotations

import mimetypes
import threading
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Asset, Folder, LibraryRoot, PhotoAlbum, PhotoAlbumAsset, ScanJob, Thumbnail, utc_now
from app.services.paths import is_docker_photos_root


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS

BATCH_SIZE = 200
PROGRESS_INTERVAL = 100
ACTIVE_SCAN_STATUSES = {"queued", "running"}


class ScanCancelled(Exception):
    pass


_cancel_events: dict[int, threading.Event] = {}
_cancel_lock = threading.Lock()


def request_cancel_scan_job(job_id: int) -> bool:
    with _cancel_lock:
        event = _cancel_events.get(job_id)
    if event:
        event.set()
        return True
    return False


def _check_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event and cancel_event.is_set():
        raise ScanCancelled


def _mark_job_cancelled(session: Session, job: ScanJob, total: int, message: str) -> None:
    job.status = "cancelled"
    job.total_assets = total
    job.processed_assets = total
    job.message = message
    job.finished_at = datetime.utcnow()
    session.add(job)
    session.commit()


def active_scan_job(session: Session, library_id: int) -> ScanJob | None:
    return session.exec(
        select(ScanJob)
        .where(ScanJob.library_id == library_id, ScanJob.status.in_(ACTIVE_SCAN_STATUSES))  # type: ignore[attr-defined]
        .order_by(ScanJob.id.desc())
    ).first()


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS


def is_supported_video(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def is_supported_media(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def relative_posix(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    return "" if str(relative) == "." else relative.as_posix()


EXIF_TAGS = {value: key for key, value in ExifTags.TAGS.items()}
GPS_TAGS = {value: key for key, value in ExifTags.GPSTAGS.items()}


def get_image_metadata(path: Path) -> dict[str, Any]:
    metadata = empty_asset_metadata()
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            transposed = ImageOps.exif_transpose(image)
            metadata["width"], metadata["height"] = transposed.size
            metadata.update(extract_exif_metadata(exif))
    except (OSError, UnidentifiedImageError):
        pass
    return metadata


def empty_asset_metadata() -> dict[str, Any]:
    return {
        "width": None,
        "height": None,
        "captured_at": None,
        "camera_make": None,
        "camera_model": None,
        "lens_model": None,
        "iso": None,
        "aperture": None,
        "exposure_time": None,
        "focal_length": None,
        "latitude": None,
        "longitude": None,
    }


def extract_exif_metadata(exif: Image.Exif) -> dict[str, Any]:
    if not exif:
        return {}
    captured_at = parse_exif_datetime(first_exif_value(exif, "DateTimeOriginal", "DateTimeDigitized", "DateTime"))
    latitude, longitude = extract_gps_coordinates(exif)
    return {
        "captured_at": captured_at,
        "camera_make": clean_exif_text(first_exif_value(exif, "Make")),
        "camera_model": clean_exif_text(first_exif_value(exif, "Model")),
        "lens_model": clean_exif_text(first_exif_value(exif, "LensModel")),
        "iso": parse_exif_int(first_exif_value(exif, "ISOSpeedRatings", "PhotographicSensitivity")),
        "aperture": format_aperture(first_exif_value(exif, "FNumber")),
        "exposure_time": format_exposure_time(first_exif_value(exif, "ExposureTime")),
        "focal_length": format_focal_length(first_exif_value(exif, "FocalLength")),
        "latitude": latitude,
        "longitude": longitude,
    }


def first_exif_value(exif: Image.Exif, *tag_names: str) -> Any:
    for tag_name in tag_names:
        tag_id = EXIF_TAGS.get(tag_name)
        if tag_id is None:
            continue
        value = exif.get(tag_id)
        if value not in (None, ""):
            return value
    return None


def clean_exif_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip("\x00")
    return text or None


def parse_exif_datetime(value: Any) -> datetime | None:
    text = clean_exif_text(value)
    if not text:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_exif_int(value: Any) -> int | None:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def ratio_to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, tuple) and len(value) == 2:
            return float(Fraction(value[0], value[1]))
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def extract_gps_coordinates(exif: Image.Exif) -> tuple[float | None, float | None]:
    gps = gps_ifd(exif)
    if not gps:
        return None, None
    latitude = parse_gps_coordinate(gps.get(GPS_TAGS.get("GPSLatitude")), gps.get(GPS_TAGS.get("GPSLatitudeRef")))
    longitude = parse_gps_coordinate(gps.get(GPS_TAGS.get("GPSLongitude")), gps.get(GPS_TAGS.get("GPSLongitudeRef")))
    return latitude, longitude


def gps_ifd(exif: Image.Exif) -> dict[int, Any]:
    try:
        return dict(exif.get_ifd(ExifTags.IFD.GPSInfo))
    except (AttributeError, KeyError, TypeError, ValueError):
        gps_tag = EXIF_TAGS.get("GPSInfo")
        raw_gps = exif.get(gps_tag) if gps_tag is not None else None
        return raw_gps if isinstance(raw_gps, dict) else {}


def parse_gps_coordinate(value: Any, ref: Any) -> float | None:
    if not value or len(value) < 3:
        return None
    degrees = ratio_to_float(value[0])
    minutes = ratio_to_float(value[1])
    seconds = ratio_to_float(value[2])
    if degrees is None or minutes is None or seconds is None:
        return None
    coordinate = degrees + minutes / 60 + seconds / 3600
    if clean_exif_text(ref) in {"S", "W"}:
        coordinate *= -1
    return round(coordinate, 7)


def format_aperture(value: Any) -> str | None:
    number = ratio_to_float(value)
    if not number:
        return None
    return f"f/{number:.1f}".rstrip("0").rstrip(".")


def format_focal_length(value: Any) -> str | None:
    number = ratio_to_float(value)
    if not number:
        return None
    return f"{number:.0f} mm" if number >= 10 else f"{number:.1f} mm"


def format_exposure_time(value: Any) -> str | None:
    number = ratio_to_float(value)
    if not number:
        return None
    if number >= 1:
        formatted = f"{number:.1f}".rstrip("0").rstrip(".")
        return f"{formatted} s"
    denominator = round(1 / number)
    if denominator > 0:
        return f"1/{denominator} s"
    formatted = f"{number:.4f}".rstrip("0").rstrip(".")
    return f"{formatted} s"


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
        session.flush()
    cache[rel_path] = folder
    return folder


def upsert_asset(session: Session, library: LibraryRoot, folder: Folder, media_path: Path, root: Path) -> Asset:
    rel_path = relative_posix(media_path, root)
    stat = media_path.stat()
    mime_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
    asset = session.exec(select(Asset).where(Asset.library_id == library.id, Asset.path == rel_path)).first()
    needs_metadata = not asset or asset.size != stat.st_size or asset.mtime != stat.st_mtime
    metadata = {
        "width": asset.width if asset else None,
        "height": asset.height if asset else None,
        "captured_at": asset.captured_at if asset else None,
        "camera_make": asset.camera_make if asset else None,
        "camera_model": asset.camera_model if asset else None,
        "lens_model": asset.lens_model if asset else None,
        "iso": asset.iso if asset else None,
        "aperture": asset.aperture if asset else None,
        "exposure_time": asset.exposure_time if asset else None,
        "focal_length": asset.focal_length if asset else None,
        "latitude": asset.latitude if asset else None,
        "longitude": asset.longitude if asset else None,
    }
    if needs_metadata:
        metadata = get_image_metadata(media_path) if is_supported_image(media_path) else empty_asset_metadata()

    if asset:
        asset.folder_id = folder.id or 0
        asset.filename = media_path.name
        asset.mime_type = mime_type
        asset.size = stat.st_size
        asset.mtime = stat.st_mtime
        apply_asset_metadata(asset, metadata)
        asset.updated_at = utc_now()
    else:
        asset = Asset(
            library_id=library.id or 0,
            folder_id=folder.id or 0,
            filename=media_path.name,
            path=rel_path,
            mime_type=mime_type,
            size=stat.st_size,
            mtime=stat.st_mtime,
            **metadata,
        )
        session.add(asset)
    session.flush()
    return asset


def apply_asset_metadata(asset: Asset, metadata: dict[str, Any]) -> None:
    for key, value in metadata.items():
        setattr(asset, key, value)


def delete_missing_assets(session: Session, library: LibraryRoot, seen_asset_paths: set[str]) -> None:
    assets = session.exec(select(Asset).where(Asset.library_id == library.id)).all()
    stale_ids = [a.id for a in assets if a.path not in seen_asset_paths and a.id is not None]

    if not stale_ids:
        return

    thumbnails = session.exec(select(Thumbnail).where(Thumbnail.asset_id.in_(stale_ids))).all()  # type: ignore[attr-defined]
    for thumbnail in thumbnails:
        thumb_path = Path(thumbnail.path)
        if thumb_path.exists():
            thumb_path.unlink(missing_ok=True)

    session.exec(sa_delete(Thumbnail).where(Thumbnail.asset_id.in_(stale_ids)))  # type: ignore[attr-defined]
    session.exec(sa_delete(PhotoAlbumAsset).where(PhotoAlbumAsset.asset_id.in_(stale_ids)))  # type: ignore[attr-defined]

    cover_albums = session.exec(select(PhotoAlbum).where(PhotoAlbum.cover_asset_id.in_(stale_ids))).all()  # type: ignore[attr-defined]
    for album in cover_albums:
        album.cover_asset_id = None

    cover_folders = session.exec(select(Folder).where(Folder.cover_asset_id.in_(stale_ids))).all()  # type: ignore[attr-defined]
    for folder in cover_folders:
        folder.cover_asset_id = None
    session.flush()

    session.exec(sa_delete(Asset).where(Asset.id.in_(stale_ids)))  # type: ignore[attr-defined]
    session.commit()


def delete_missing_folders(session: Session, library: LibraryRoot, seen_folder_paths: set[str]) -> None:
    folders = session.exec(select(Folder).where(Folder.library_id == library.id)).all()
    stale_ids = [f.id for f in folders if f.path not in seen_folder_paths and f.id is not None]
    if stale_ids:
        session.exec(sa_delete(Folder).where(Folder.id.in_(stale_ids)))  # type: ignore[attr-defined]
    session.commit()


def refresh_folder_counts(session: Session, library: LibraryRoot) -> None:
    folders = session.exec(select(Folder).where(Folder.library_id == library.id)).all()
    if not folders:
        return

    folder_ids = [f.id for f in folders if f.id is not None]

    photo_counts = session.exec(
        select(Asset.folder_id, func.count(Asset.id))
        .where(Asset.folder_id.in_(folder_ids))  # type: ignore[attr-defined]
        .group_by(Asset.folder_id)
    ).all()
    photo_count_map = {folder_id: cnt for folder_id, cnt in photo_counts}

    subfolder_counts = session.exec(
        select(Folder.parent_id, func.count(Folder.id))
        .where(Folder.parent_id.in_(folder_ids))  # type: ignore[attr-defined]
        .group_by(Folder.parent_id)
    ).all()
    subfolder_count_map = {parent_id: cnt for parent_id, cnt in subfolder_counts}

    latest_asset_rows = session.exec(
        select(Asset.folder_id, Asset.id)
        .where(Asset.folder_id.in_(folder_ids))  # type: ignore[attr-defined]
        .order_by(Asset.folder_id, Asset.mtime.desc(), Asset.id.desc())
    ).all()
    cover_map: dict[int, int] = {}
    for folder_id, asset_id in latest_asset_rows:
        if folder_id is not None and asset_id is not None and folder_id not in cover_map:
            cover_map[folder_id] = asset_id

    folder_path_by_id = {folder.id: folder.path for folder in folders if folder.id is not None}
    current_cover_ids = [folder.cover_asset_id for folder in folders if folder.cover_asset_id is not None]
    current_cover_rows = (
        session.exec(
            select(Asset.id, Asset.folder_id).where(
                Asset.library_id == library.id,
                Asset.id.in_(current_cover_ids),  # type: ignore[attr-defined]
            )
        ).all()
        if current_cover_ids
        else []
    )
    current_cover_folder_paths = {
        asset_id: folder_path_by_id.get(folder_id)
        for asset_id, folder_id in current_cover_rows
    }

    for folder in folders:
        folder.photo_count = photo_count_map.get(folder.id, 0)
        folder.folder_count = subfolder_count_map.get(folder.id, 0)
        current_cover_path = current_cover_folder_paths.get(folder.cover_asset_id)
        if current_cover_path is None or not folder_path_contains(folder.path, current_cover_path):
            folder.cover_asset_id = cover_map.get(folder.id)
        folder.updated_at = utc_now()

    session.commit()


def folder_path_contains(parent_path: str, child_path: str) -> bool:
    return parent_path == "" or child_path == parent_path or child_path.startswith(f"{parent_path}/")


def scan_library(
    session: Session,
    library_id: int,
    job: ScanJob | None = None,
    generate_thumbnails: bool = False,
    cancel_event: threading.Event | None = None,
) -> int:
    library = session.get(LibraryRoot, library_id)
    if not library or not library.is_enabled:
        return 0
    if is_docker_photos_root(library.path):
        return 0
    try:
        root = Path(library.path).resolve()
        is_existing_directory = root.exists() and root.is_dir()
    except OSError:
        return 0
    if not is_existing_directory:
        return 0

    folder_cache: dict[str, Folder] = {}
    seen_folder_paths: set[str] = set()
    seen_asset_paths: set[str] = set()
    total = 0

    try:
        for directory, subdirs, filenames in root.walk():
            subdirs[:] = [name for name in subdirs if not name.startswith(".")]
            _check_cancelled(cancel_event)

            folder = get_or_create_folder(session, library, directory, root, folder_cache)
            seen_folder_paths.add(folder.path)
            for filename in filenames:
                _check_cancelled(cancel_event)

                media_path = directory / filename
                if not is_supported_media(media_path):
                    continue
                asset = upsert_asset(session, library, folder, media_path, root)
                seen_asset_paths.add(asset.path)
                total += 1

                if job and total % PROGRESS_INTERVAL == 0:
                    job.processed_assets = total
                    session.add(job)
                    session.commit()
                elif total % BATCH_SIZE == 0:
                    session.commit()

        session.commit()

    except ScanCancelled:
        session.commit()

        if job:
            _mark_job_cancelled(session, job, total, f"Scan cancelled after {total} items")

        return total

    if job:
        job.processed_assets = total
        session.add(job)
        session.commit()

    delete_missing_assets(session, library, seen_asset_paths)
    delete_missing_folders(session, library, seen_folder_paths)
    refresh_folder_counts(session, library)
    library.last_scan_at = utc_now()
    session.commit()

    if generate_thumbnails and total > 0:
        try:
            _check_cancelled(cancel_event)

            image_assets = session.exec(
                select(Asset).where(
                    Asset.library_id == library_id,
                    Asset.mime_type.like("image/%"),
                )
            ).all()
            if image_assets:
                from app.services.thumbnails import bulk_generate_thumbnails

                thumb_count = 0
                asset_ids = [a.id for a in image_assets if a.id is not None]
                for size in ("small", "medium"):
                    _check_cancelled(cancel_event)
                    thumb_count += bulk_generate_thumbnails(
                        session,
                        asset_ids,
                        size=size,
                        cancel_event=cancel_event,
                    )
                if job:
                    job.message = f"Indexed {total} media items, {thumb_count} thumbnails generated"
                    session.add(job)
                    session.commit()
        except ScanCancelled:
            if job:
                _mark_job_cancelled(
                    session,
                    job,
                    total,
                    f"Indexed {total} media items (thumbnail generation cancelled)",
                )

    return total


def run_scan_job(session: Session, job_id: int, generate_thumbnails: bool = False) -> None:
    cancel_event = threading.Event()
    with _cancel_lock:
        _cancel_events[job_id] = cancel_event

    job = session.get(ScanJob, job_id)
    if not job:
        with _cancel_lock:
            _cancel_events.pop(job_id, None)
        return

    try:
        session.refresh(job)
        if job.status == "cancelled":
            return
        if cancel_event.is_set():
            _mark_job_cancelled(session, job, 0, "Scan cancelled before start")
            return

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.total_estimated = None
        job.processed_assets = 0
        session.commit()

        total = scan_library(
            session, job.library_id, job=job, generate_thumbnails=generate_thumbnails, cancel_event=cancel_event
        )
    except ScanCancelled:
        return
    except Exception as exc:  # pragma: no cover - defensive status reporting
        job.status = "failed"
        job.message = str(exc)
        job.finished_at = datetime.utcnow()
        session.commit()
        raise
    finally:
        with _cancel_lock:
            _cancel_events.pop(job_id, None)

    if job.status == "running":
        job.status = "completed"
        job.total_assets = total
        if "thumbnails generated" not in job.message:
            job.message = f"Indexed {total} media items"
        job.finished_at = datetime.utcnow()
    session.commit()
