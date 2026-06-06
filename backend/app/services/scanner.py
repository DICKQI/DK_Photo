from __future__ import annotations

import concurrent.futures
import mimetypes
import threading
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, UnidentifiedImageError
from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlmodel import Session, select

try:
    import exifread as _exifread_lib
    _HAS_EXIFREAD = True
except ImportError:
    _HAS_EXIFREAD = False

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
    exif_data: dict[str, Any] = {}
    orientation: int | None = None

    if _HAS_EXIFREAD:
        try:
            with open(path, "rb") as fh:
                tags = _exifread_lib.process_file(fh, details=False)
            if tags:
                exif_data = _parse_exifread_tags(tags)
                orientation = exif_data.pop("_orientation", None)
        except Exception:
            pass

    try:
        with Image.open(path) as image:
            raw_width, raw_height = image.size

            if not exif_data:
                pillow_exif = image.getexif()
                if pillow_exif:
                    exif_data = extract_exif_metadata(pillow_exif)
                    if orientation is None:
                        orientation = _pillow_orientation(pillow_exif)

            if orientation in (5, 6, 7, 8):
                metadata["width"], metadata["height"] = raw_height, raw_width
            else:
                metadata["width"], metadata["height"] = raw_width, raw_height

    except (OSError, UnidentifiedImageError):
        return metadata

    metadata.update(exif_data)
    return metadata


def _pillow_orientation(exif: Image.Exif) -> int | None:
    tag_id = EXIF_TAGS.get("Orientation")
    if tag_id is None:
        return None
    value = exif.get(tag_id)
    return parse_exif_int(value)


def _parse_exifread_tags(tags: dict) -> dict[str, Any]:
    result: dict[str, Any] = {}

    def _text(*keys: str) -> str | None:
        for key in keys:
            v = _exifread_text(tags, key)
            if v:
                return v
        return None

    def _number(*keys: str) -> int | None:
        for key in keys:
            v = _exifread_number(tags, key)
            if v is not None:
                return v
        return None

    def _ratio(*keys: str) -> float | None:
        for key in keys:
            v = _exifread_ratio(tags, key)
            if v is not None:
                return v
        return None

    make = _text("Image Make")
    if make:
        result["camera_make"] = make

    model = _text("Image Model")
    if model:
        result["camera_model"] = model

    lens = _text("EXIF LensModel", "Image LensModel")
    if lens:
        result["lens_model"] = lens

    dt_text = _text("EXIF DateTimeOriginal", "Image DateTimeOriginal", "Image DateTime")
    if dt_text:
        captured = parse_exif_datetime(dt_text)
        if captured:
            result["captured_at"] = captured

    iso_val = _number("EXIF ISOSpeedRatings", "Image ISOSpeedRatings", "EXIF PhotographicSensitivity")
    if iso_val is not None:
        iso = parse_exif_int(iso_val)
        if iso is not None:
            result["iso"] = iso

    fnumber = _ratio("EXIF FNumber", "Image FNumber")
    if fnumber is not None:
        result["aperture"] = format_aperture(fnumber)

    exposure = _ratio("EXIF ExposureTime", "Image ExposureTime")
    if exposure is not None:
        result["exposure_time"] = format_exposure_time(exposure)

    focal = _ratio("EXIF FocalLength", "Image FocalLength")
    if focal is not None:
        result["focal_length"] = format_focal_length(focal)

    lat, lon = _exifread_gps(tags)
    if lat is not None:
        result["latitude"] = lat
    if lon is not None:
        result["longitude"] = lon

    orientation = _number("Image Orientation")
    if orientation is not None:
        result["_orientation"] = parse_exif_int(orientation)

    return result


def _exifread_text(tags: dict, key: str) -> str | None:
    tag = tags.get(key)
    if tag is None:
        return None
    return clean_exif_text(str(tag))


def _exifread_number(tags: dict, key: str) -> int | None:
    tag = tags.get(key)
    if tag is None:
        return None
    try:
        values = tag.values
        if values and len(values) > 0:
            return int(values[0])
    except (TypeError, ValueError):
        pass
    return None


def _exifread_ratio(tags: dict, key: str) -> float | None:
    tag = tags.get(key)
    if tag is None:
        return None
    try:
        values = tag.values
        if values and len(values) > 0:
            item = values[0]
            if hasattr(item, "num") and hasattr(item, "den"):
                return float(Fraction(item.num, item.den))  # type: ignore[arg-type]
            return float(item)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return None


def _exifread_gps(tags: dict) -> tuple[float | None, float | None]:
    lat_ref_tag = tags.get("GPS GPSLatitudeRef")
    lat_tag = tags.get("GPS GPSLatitude")
    lon_ref_tag = tags.get("GPS GPSLongitudeRef")
    lon_tag = tags.get("GPS GPSLongitude")

    latitude = _exifread_gps_coord(lat_tag, str(lat_ref_tag) if lat_ref_tag else "")
    longitude = _exifread_gps_coord(lon_tag, str(lon_ref_tag) if lon_ref_tag else "")
    return latitude, longitude


def _exifread_gps_coord(
    coord_tag: object | None,
    ref: str,
) -> float | None:
    if coord_tag is None:
        return None
    try:
        values = coord_tag.values  # type: ignore[union-attr]
        if not values or len(values) < 3:
            return None

        def _ratio_to_float(item: Any) -> float | None:
            if hasattr(item, "num") and hasattr(item, "den"):
                return float(Fraction(item.num, item.den))  # type: ignore[arg-type]
            return float(item)

        degrees = _ratio_to_float(values[0])
        minutes = _ratio_to_float(values[1])
        seconds = _ratio_to_float(values[2])
        if degrees is None or minutes is None or seconds is None:
            return None
        coord = degrees + minutes / 60 + seconds / 3600
        if ref.strip().upper() in {"S", "W"}:
            coord *= -1
        return round(coord, 7)
    except Exception:
        return None


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


def _count_media_files(root: Path) -> int:
    count = 0
    for _directory, subdirs, filenames in root.walk():
        subdirs[:] = [name for name in subdirs if not name.startswith(".")]
        for filename in filenames:
            if Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS:
                count += 1
    return count


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

    if job and job.total_estimated is None:
        job.total_estimated = _count_media_files(root)
        session.add(job)
        session.commit()

    folder_cache: dict[str, Folder] = {}
    seen_folder_paths: set[str] = set()
    seen_asset_paths: set[str] = set()
    total = 0
    thumb_results: list[dict] = []
    pending_images: list[Asset] = []
    completed_thumbs: set[tuple[int, str]] = set()
    executor: concurrent.futures.ThreadPoolExecutor | None = None
    thumb_futures: list[concurrent.futures.Future] = []

    if generate_thumbnails:
        from app.config import get_thumb_workers

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=get_thumb_workers())

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

                if generate_thumbnails and asset.mime_type.startswith("image/"):
                    pending_images.append(asset)

                if total % BATCH_SIZE == 0:
                    session.commit()
                    if generate_thumbnails and pending_images and executor:
                        _submit_pending_thumbnails(
                            executor,
                            pending_images,
                            library.path,
                            completed_thumbs,
                            thumb_futures,
                        )
                        pending_images.clear()

                if job and total % PROGRESS_INTERVAL == 0:
                    job.processed_assets = total
                    session.add(job)
                    session.commit()

        session.commit()

        if generate_thumbnails and pending_images and executor:
            _submit_pending_thumbnails(
                executor,
                pending_images,
                library.path,
                completed_thumbs,
                thumb_futures,
            )
            pending_images.clear()

        if generate_thumbnails and executor:
            _collect_thumbnail_results(thumb_futures, thumb_results, cancel_event)
            thumb_futures.clear()

    except ScanCancelled:
        session.commit()

        if generate_thumbnails and executor:
            executor.shutdown(wait=False, cancel_futures=True)

        if job:
            _mark_job_cancelled(session, job, total, f"Scan cancelled after {total} items")

        return total
    finally:
        if executor:
            executor.shutdown(wait=False)

    if job:
        job.processed_assets = total
        session.add(job)
        session.commit()

    delete_missing_assets(session, library, seen_asset_paths)
    delete_missing_folders(session, library, seen_folder_paths)
    refresh_folder_counts(session, library)
    library.last_scan_at = utc_now()
    session.commit()

    if generate_thumbnails and total > 0 and thumb_results:
        from app.services.thumbnails import flush_thumbnails

        flush_thumbnails(session, thumb_results)
        thumb_count = len(thumb_results)
        if job:
            job.message = f"Indexed {total} media items, {thumb_count} thumbnails generated"
            session.add(job)
            session.commit()
    elif job and generate_thumbnails and total > 0 and not thumb_results:
        if "thumbnails generated" not in job.message:
            job.message = f"Indexed {total} media items"
            session.add(job)
            session.commit()

    return total


def _submit_pending_thumbnails(
    executor: concurrent.futures.ThreadPoolExecutor,
    pending: list[Asset],
    library_path: str,
    completed: set[tuple[int, str]],
    futures_out: list[concurrent.futures.Future],
) -> None:
    from app.services.thumbnails import generate_thumbnail_disk_only

    for asset in pending:
        for size in ("small", "medium"):
            key = (asset.id or 0, size)
            if key in completed:
                continue
            completed.add(key)
            future = executor.submit(
                generate_thumbnail_disk_only,
                asset_id=asset.id or 0,
                library_path=library_path,
                asset_path=asset.path,
                mtime=asset.mtime,
                mime_type=asset.mime_type,
                size=size,
            )
            futures_out.append(future)


def _collect_thumbnail_results(
    futures: list[concurrent.futures.Future],
    results: list[dict],
    cancel_event: threading.Event | None,
) -> None:
    for future in concurrent.futures.as_completed(futures):
        _check_cancelled(cancel_event)
        try:
            result = future.result()
            if result:
                results.append(result)
        except Exception:
            pass


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
