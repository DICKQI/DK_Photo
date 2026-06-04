from __future__ import annotations

import mimetypes
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Asset, Folder, LibraryRoot, PhotoAlbum, PhotoAlbumAsset, ScanJob, Thumbnail, utc_now


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS


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
        session.commit()
        session.refresh(folder)
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
    session.commit()
    session.refresh(asset)
    return asset


def apply_asset_metadata(asset: Asset, metadata: dict[str, Any]) -> None:
    for key, value in metadata.items():
        setattr(asset, key, value)


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
        album_assets = session.exec(select(PhotoAlbumAsset).where(PhotoAlbumAsset.asset_id == asset.id)).all()
        for album_asset in album_assets:
            session.delete(album_asset)
        cover_albums = session.exec(select(PhotoAlbum).where(PhotoAlbum.cover_asset_id == asset.id)).all()
        for album in cover_albums:
            album.cover_asset_id = None
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
            media_path = directory / filename
            if not is_supported_media(media_path):
                continue
            asset = upsert_asset(session, library, folder, media_path, root)
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
    job.message = f"Indexed {total} media items"
    job.finished_at = datetime.utcnow()
    session.commit()
