from __future__ import annotations

import concurrent.futures
import itertools
import logging
import mimetypes
import os
import queue
import threading
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image

_max_pixels_env = os.getenv("DK_PHOTO_MAX_IMAGE_PIXELS", "")
if _max_pixels_env:
    Image.MAX_IMAGE_PIXELS = int(_max_pixels_env)
elif Image.MAX_IMAGE_PIXELS is not None:
    Image.MAX_IMAGE_PIXELS = max(Image.MAX_IMAGE_PIXELS, 500_000_000)
from sqlalchemy import delete as sa_delete
from sqlalchemy import func
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

from app.models import Asset, Folder, LibraryRoot, PhotoAlbum, PhotoAlbumAsset, ProcessingError, ScanJob, Thumbnail, utc_now
from app.services.paths import is_docker_photos_root


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS

BATCH_SIZE = 200
PROGRESS_INTERVAL = 100
ACTIVE_SCAN_STATUSES = {"queued", "running"}
THUMBNAIL_READY_SIZES = ("small", "medium")
DELETE_CHUNK_SIZE = 900
THUMBNAIL_PRIORITY = 10
METADATA_PRIORITY = 0


class PriorityExecutor:
    def __init__(self, max_workers: int) -> None:
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._counter = itertools.count()
        self._shutdown = False
        self._lock = threading.Lock()
        self._workers = [
            threading.Thread(target=self._worker, daemon=True)
            for _ in range(max(1, max_workers))
        ]
        for worker in self._workers:
            worker.start()

    def submit(self, fn, *args, priority: int = 0, **kwargs) -> concurrent.futures.Future:
        with self._lock:
            if self._shutdown:
                raise RuntimeError("cannot schedule new futures after shutdown")
            future: concurrent.futures.Future = concurrent.futures.Future()
            self._queue.put((priority, next(self._counter), future, fn, args, kwargs))
            return future

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            if cancel_futures:
                while True:
                    try:
                        _priority, _seq, future, _fn, _args, _kwargs = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    if future is not None:
                        future.cancel()
                    self._queue.task_done()
            for _worker in self._workers:
                self._queue.put((10_000, next(self._counter), None, None, (), {}))
        if wait:
            for worker in self._workers:
                worker.join()

    def _worker(self) -> None:
        while True:
            _priority, _seq, future, fn, args, kwargs = self._queue.get()
            try:
                if future is None:
                    return
                if not future.set_running_or_notify_cancel():
                    continue
                try:
                    future.set_result(fn(*args, **kwargs))
                except BaseException as exc:
                    future.set_exception(exc)
            finally:
                self._queue.task_done()


@dataclass(slots=True)
class CacheEntry:
    id: int
    size: int
    mtime: float


@dataclass(slots=True)
class _ThumbAsset:
    id: int
    path: str
    mtime: float
    mime_type: str


@dataclass
class MediaCounts:
    total: int = 0
    images: int = 0
    videos: int = 0


class ScanCancelled(Exception):
    pass


_cancel_events: dict[int, threading.Event] = {}
_cancel_lock = threading.Lock()

_scan_creation_locks: dict[int, threading.Lock] = {}
_scan_creation_locks_lock = threading.Lock()


def acquire_scan_creation_lock(library_id: int) -> threading.Lock:
    with _scan_creation_locks_lock:
        lock = _scan_creation_locks.get(library_id)
        if lock is None:
            lock = threading.Lock()
            _scan_creation_locks[library_id] = lock
    lock.acquire()
    return lock


def release_scan_creation_lock(lock: threading.Lock) -> None:
    lock.release()


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


def _mark_job_cancelled(
    session: Session,
    job: ScanJob,
    total: int,
    message: str,
    images: int = 0,
    videos: int = 0,
    thumbnail_ready_images: int = 0,
) -> None:
    job.status = "cancelled"
    job.total_assets = total
    job.processed_assets = total
    job.processed_images = images
    job.processed_videos = videos
    job.thumbnail_ready_images = thumbnail_ready_images
    job.message = message
    job.finished_at = utc_now()
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
            raw_width, raw_height = image.size

            pillow_exif = image.getexif()
            if pillow_exif:
                exif_data = extract_exif_metadata(pillow_exif)
                metadata.update(exif_data)
                orientation = _pillow_orientation(pillow_exif)
            else:
                orientation = None

            if orientation in (5, 6, 7, 8):
                metadata["width"], metadata["height"] = raw_height, raw_width
            else:
                metadata["width"], metadata["height"] = raw_width, raw_height

    except Exception:
        logger.warning("Failed to read image metadata for %s", path, exc_info=True)
        return None

    return metadata


def _pillow_orientation(exif: Image.Exif) -> int | None:
    tag_id = EXIF_TAGS.get("Orientation")
    if tag_id is None:
        return None
    value = exif.get(tag_id)
    return parse_exif_int(value)


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


def _apply_metadata_to_asset(
    session: Session,
    library_id: int,
    entry: CacheEntry | None,
    folder_id: int,
    filename: str,
    rel: str,
    size: int,
    mtime: float,
    mime_type: str,
    metadata: dict[str, Any],
) -> Asset:
    if entry is not None:
        asset = session.get(Asset, entry.id)
    else:
        asset = session.exec(
            select(Asset).where(Asset.library_id == library_id, Asset.path == rel)
        ).first()

    if asset:
        asset.folder_id = folder_id
        asset.filename = filename
        asset.mime_type = mime_type
        asset.size = size
        asset.mtime = mtime
        apply_asset_metadata(asset, metadata)
        asset.updated_at = utc_now()
    else:
        asset = Asset(
            library_id=library_id,
            folder_id=folder_id,
            filename=filename,
            path=rel,
            mime_type=mime_type,
            size=size,
            mtime=mtime,
            **metadata,
        )
        session.add(asset)
    return asset


def upsert_asset(
    session: Session,
    library: LibraryRoot,
    folder: Folder,
    media_path: Path,
    root: Path,
    entry: CacheEntry | None = None,
) -> Asset:
    rel_path = relative_posix(media_path, root)
    stat = media_path.stat()
    mime_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
    if entry is not None:
        asset = session.get(Asset, entry.id)
        needs_metadata = entry.size != stat.st_size or entry.mtime != stat.st_mtime
    else:
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
        if is_supported_image(media_path):
            img_meta = get_image_metadata(media_path)
            if img_meta is None:
                metadata = empty_asset_metadata()
                session.add(
                    ProcessingError(
                        library_id=library.id or 0,
                        asset_path=rel_path,
                        filename=media_path.name,
                        error_type="metadata",
                        error_message=f"无法读取图片元数据：{media_path.name}",
                    )
                )
                session.commit()
            else:
                metadata = img_meta
        else:
            metadata = empty_asset_metadata()

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


def _chunks(items: list[int], size: int = DELETE_CHUNK_SIZE):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def delete_missing_assets(session: Session, library: LibraryRoot, stale_ids: list[int]) -> None:
    if not stale_ids:
        return

    for chunk in _chunks(stale_ids):
        thumbnails = session.exec(select(Thumbnail).where(Thumbnail.asset_id.in_(chunk))).all()  # type: ignore[attr-defined]
        for thumbnail in thumbnails:
            thumb_path = Path(thumbnail.path)
            if thumb_path.exists():
                thumb_path.unlink(missing_ok=True)

        session.exec(sa_delete(Thumbnail).where(Thumbnail.asset_id.in_(chunk)))  # type: ignore[attr-defined]
        session.exec(sa_delete(PhotoAlbumAsset).where(PhotoAlbumAsset.asset_id.in_(chunk)))  # type: ignore[attr-defined]

        cover_albums = session.exec(select(PhotoAlbum).where(PhotoAlbum.cover_asset_id.in_(chunk))).all()  # type: ignore[attr-defined]
        for album in cover_albums:
            album.cover_asset_id = None

        cover_folders = session.exec(select(Folder).where(Folder.cover_asset_id.in_(chunk))).all()  # type: ignore[attr-defined]
        for folder in cover_folders:
            folder.cover_asset_id = None
        session.flush()

        session.exec(sa_delete(Asset).where(Asset.id.in_(chunk)))  # type: ignore[attr-defined]
        session.commit()


def delete_missing_folders(session: Session, library: LibraryRoot, stale_ids: list[int]) -> None:
    for chunk in _chunks(stale_ids):
        session.exec(sa_delete(Folder).where(Folder.id.in_(chunk)))  # type: ignore[attr-defined]
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


def _count_media_files(root: Path) -> MediaCounts:
    counts = MediaCounts()
    for _directory, subdirs, filenames in root.walk():
        subdirs[:] = [name for name in subdirs if not name.startswith(".")]
        for filename in filenames:
            suffix = Path(filename).suffix.lower()
            if suffix in SUPPORTED_IMAGE_EXTENSIONS:
                counts.total += 1
                counts.images += 1
            elif suffix in SUPPORTED_VIDEO_EXTENSIONS:
                counts.total += 1
                counts.videos += 1
    return counts


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

    # Preload existing assets into a lightweight cache for O(1) lookup.
    # Pop on visit; entries left behind after the walk are stale.
    remaining: dict[str, CacheEntry] = {}
    duplicate_ids: list[int] = []
    for row in session.exec(
        select(Asset.id, Asset.path, Asset.size, Asset.mtime)
        .where(Asset.library_id == library.id)
    ):
        asset_id, path_str, size, mtime = row
        if path_str in remaining:
            duplicate_ids.append(asset_id)
            continue
        remaining[path_str] = CacheEntry(id=asset_id, size=size, mtime=mtime)

    if duplicate_ids:
        logger.warning(
            "Found %d duplicate asset paths in library %d. Excess rows will be cleaned up.",
            len(duplicate_ids), library.id or 0,
        )

    # Preload existing folders into the lookup cache.
    folder_cache: dict[str, Folder] = {
        f.path: f for f in session.exec(select(Folder).where(Folder.library_id == library.id))
    }
    seen_folder_paths: set[str] = set()
    seen_asset_paths: set[str] = set()
    future_contexts: dict[concurrent.futures.Future, dict] = {}
    total = 0
    image_total = 0
    video_total = 0
    thumbnail_ready_images = 0
    pending_images: list[Asset | _ThumbAsset] = []
    completed_thumbs: set[tuple[int, str]] = set()
    ready_thumb_sizes: dict[int, set[str]] = {}
    ready_thumb_assets: set[int] = set()
    from app.config import get_thumb_workers
    worker_budget = get_thumb_workers()
    executor = PriorityExecutor(max_workers=worker_budget)
    thumb_futures: list[concurrent.futures.Future] = []
    meta_pending: list[dict] = []
    MAX_THUMB_OUTSTANDING = worker_budget * 4
    THUMB_ASSET_CHUNK = max(1, worker_budget * 2)

    def flush_thumbnail_work(wait_for_slot: bool = False) -> None:
        nonlocal thumbnail_ready_images
        if not generate_thumbnails:
            return
        while pending_images and len(thumb_futures) < MAX_THUMB_OUTSTANDING:
            limit = min(
                THUMB_ASSET_CHUNK,
                len(pending_images),
                max(1, (MAX_THUMB_OUTSTANDING - len(thumb_futures) + 1) // 2),
            )
            chunk = pending_images[:limit]
            del pending_images[:limit]
            _submit_pending_thumbnails(
                executor,
                chunk,
                library.path,
                completed_thumbs,
                thumb_futures,
                future_contexts,
            )
        if thumb_futures:
            thumbnail_ready_images += _flush_completed_thumbnail_progress(
                session,
                thumb_futures,
                ready_thumb_sizes,
                ready_thumb_assets,
                cancel_event,
                library_id=library.id or 0,
                job_id=job.id if job else None,
                future_contexts=future_contexts,
                wait_for_one=wait_for_slot and len(thumb_futures) >= MAX_THUMB_OUTSTANDING,
            )
            _clean_future_contexts(future_contexts, thumb_futures)

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
                rel = relative_posix(media_path, root)
                is_image = is_supported_image(media_path)
                is_video = is_supported_video(media_path)
                try:
                    entry = remaining.pop(rel, None)
                    stat = media_path.stat()
                    mime_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"

                    if entry is not None and entry.size == stat.st_size and entry.mtime == stat.st_mtime:
                        # Unchanged asset: skip metadata extraction and DB write.
                        seen_asset_paths.add(rel)
                        total += 1
                        if is_image:
                            image_total += 1
                            if generate_thumbnails:
                                pending_images.append(
                                    _ThumbAsset(id=entry.id, path=rel, mtime=stat.st_mtime, mime_type=mime_type)
                                )
                        elif is_video:
                            video_total += 1
                        if len(pending_images) >= THUMB_ASSET_CHUNK:
                            flush_thumbnail_work(wait_for_slot=True)
                        if job and total % PROGRESS_INTERVAL == 0:
                            _update_scan_job_progress(
                                session, job, total, image_total, video_total, thumbnail_ready_images,
                            )
                            session.commit()
                        continue

                    # Changed or new asset: collect for batch metadata extraction.
                    meta_pending.append({
                        "entry": entry,
                        "folder_id": folder.id or 0,
                        "filename": media_path.name,
                        "rel": rel,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "mime_type": mime_type,
                        "is_image": is_image,
                        "media_path": media_path,
                    })
                except OSError:
                    logger.warning("Skipping file: %s", media_path)
                    remaining.pop(rel, None)
                    seen_asset_paths.add(rel)
                    session.add(
                        ProcessingError(
                            library_id=library.id or 0,
                            scan_job_id=job.id if job else None,
                            asset_path=rel,
                            filename=media_path.name,
                            error_type="file_access",
                            error_message=f"无法访问文件：{media_path}",
                        )
                    )
                    session.commit()
                    continue

                if len(meta_pending) >= BATCH_SIZE:
                    _flush_meta_pending(
                        executor, meta_pending, session, library.id or 0,
                        seen_asset_paths, pending_images, generate_thumbnails,
                        cancel_event, job.id if job else None,
                    )
                    for ctx in meta_pending:
                        total += 1
                        if ctx["is_image"]:
                            image_total += 1
                        else:
                            video_total += 1
                    meta_pending.clear()

                    flush_thumbnail_work()

                    if job:
                        _update_scan_job_progress(
                            session, job, total, image_total, video_total, thumbnail_ready_images,
                        )
                    session.commit()

                    # Thumbnail backpressure
                    if generate_thumbnails:
                        while len(thumb_futures) >= MAX_THUMB_OUTSTANDING:
                            flush_thumbnail_work(wait_for_slot=True)
                            if job:
                                _update_scan_job_progress(
                                    session, job, total, image_total, video_total, thumbnail_ready_images,
                                )
                                session.commit()

        # Flush remaining meta_pending after walk completes.
        if meta_pending:
            _flush_meta_pending(
                executor, meta_pending, session, library.id or 0,
                seen_asset_paths, pending_images, generate_thumbnails,
                cancel_event, job.id if job else None,
            )
            for ctx in meta_pending:
                total += 1
                if ctx["is_image"]:
                    image_total += 1
                else:
                    video_total += 1
            meta_pending.clear()

        session.commit()

        if generate_thumbnails:
            while pending_images or thumb_futures:
                flush_thumbnail_work(wait_for_slot=True)
                if not pending_images and thumb_futures:
                    thumbnail_ready_images += _flush_completed_thumbnail_progress(
                        session,
                        thumb_futures,
                        ready_thumb_sizes,
                        ready_thumb_assets,
                        cancel_event,
                        wait=True,
                        library_id=library.id or 0,
                        job_id=job.id if job else None,
                        future_contexts=future_contexts,
                    )
                    _clean_future_contexts(future_contexts, thumb_futures)
                    thumb_futures.clear()

        if job:
            _update_scan_job_progress(
                session, job, total, image_total, video_total, thumbnail_ready_images,
            )
            session.commit()

    except ScanCancelled:
        session.commit()

        if generate_thumbnails:
            thumbnail_ready_images += _flush_completed_thumbnail_progress(
                session,
                thumb_futures,
                ready_thumb_sizes,
                ready_thumb_assets,
                None,
                library_id=library.id or 0,
                job_id=job.id if job else None,
                future_contexts=future_contexts,
            )
            executor.shutdown(wait=False, cancel_futures=True)

        if job:
            _mark_job_cancelled(
                session,
                job,
                total,
                f"Scan cancelled after {total} items",
                image_total,
                video_total,
                thumbnail_ready_images,
            )

        return total
    finally:
        executor.shutdown(wait=False)

    stale_asset_ids = [e.id for e in remaining.values()] + duplicate_ids
    delete_missing_assets(session, library, stale_asset_ids)

    stale_folder_ids: list[int] = []
    for f in folder_cache.values():
        if f.path not in seen_folder_paths and f.id is not None:
            stale_folder_ids.append(f.id)
    delete_missing_folders(session, library, stale_folder_ids)
    refresh_folder_counts(session, library)
    library.last_scan_at = utc_now()
    session.commit()

    if job:
        if generate_thumbnails and image_total > 0:
            job.thumbnail_ready_images = thumbnail_ready_images
            job.message = f"Indexed {total} media items, {thumbnail_ready_images} thumbnail-ready images"
        else:
            job.message = f"Indexed {total} media items"
        session.add(job)
        session.commit()

    return total


def _flush_meta_pending(
    executor: PriorityExecutor,
    contexts: list[dict],
    session: Session,
    library_id: int,
    seen_asset_paths: set[str],
    pending_images: list[Asset | _ThumbAsset],
    generate_thumbnails: bool,
    cancel_event: threading.Event | None = None,
    job_id: int | None = None,
) -> None:
    if not contexts:
        return
    futures_to_index: dict[concurrent.futures.Future, int] = {}
    metadata_by_index: dict[int, dict[str, Any]] = {}
    for index, ctx in enumerate(contexts):
        if ctx["is_image"]:
            fut = executor.submit(get_image_metadata, ctx["media_path"], priority=METADATA_PRIORITY)
            futures_to_index[fut] = index
        else:
            metadata_by_index[index] = empty_asset_metadata()

    for fut in concurrent.futures.as_completed(futures_to_index):
        index = futures_to_index[fut]
        ctx = contexts[index]
        try:
            metadata = fut.result()
        except Exception:
            metadata = None
        if metadata is None:
            session.add(
                ProcessingError(
                    library_id=library_id,
                    scan_job_id=job_id,
                    asset_path=ctx["rel"],
                    filename=ctx["filename"],
                    error_type="metadata",
                    error_message=f"无法读取图片元数据：{ctx['filename']}",
                )
            )
            metadata = empty_asset_metadata()
        metadata_by_index[index] = metadata

    for index, ctx in enumerate(contexts):
        _apply_metadata_context(
            session,
            library_id,
            ctx,
            metadata_by_index[index],
            seen_asset_paths,
            pending_images,
            generate_thumbnails,
        )


def _apply_metadata_context(
    session: Session,
    library_id: int,
    ctx: dict,
    metadata: dict[str, Any],
    seen_asset_paths: set[str],
    pending_images: list[Asset | _ThumbAsset],
    generate_thumbnails: bool,
) -> None:
    asset = _apply_metadata_to_asset(
        session,
        library_id,
        ctx["entry"],
        ctx["folder_id"],
        ctx["filename"],
        ctx["rel"],
        ctx["size"],
        ctx["mtime"],
        ctx["mime_type"],
        metadata,
    )
    seen_asset_paths.add(asset.path)
    if generate_thumbnails and ctx["is_image"]:
        pending_images.append(asset)


def _submit_pending_thumbnails(
    executor: PriorityExecutor,
    pending: list[Asset | _ThumbAsset],
    library_path: str,
    completed: set[tuple[int, str]],
    futures_out: list[concurrent.futures.Future],
    future_contexts: dict[concurrent.futures.Future, dict] | None = None,
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
                priority=THUMBNAIL_PRIORITY,
            )
            futures_out.append(future)
            if future_contexts is not None:
                future_contexts[future] = {
                    "asset_id": asset.id or 0,
                    "asset_path": asset.path,
                    "size": size,
                }


def _update_scan_job_progress(
    session: Session,
    job: ScanJob,
    total: int,
    images: int,
    videos: int,
    thumbnail_ready_images: int,
) -> None:
    job.processed_assets = total
    job.processed_images = images
    job.processed_videos = videos
    job.thumbnail_ready_images = thumbnail_ready_images
    session.add(job)


def _flush_completed_thumbnail_progress(
    session: Session,
    futures: list[concurrent.futures.Future],
    ready_sizes: dict[int, set[str]],
    ready_assets: set[int],
    cancel_event: threading.Event | None,
    wait: bool = False,
    library_id: int | None = None,
    job_id: int | None = None,
    future_contexts: dict[concurrent.futures.Future, dict] | None = None,
    wait_for_one: bool = False,
) -> int:
    results = _collect_thumbnail_results(futures, cancel_event, wait, future_contexts, wait_for_one)
    if not results:
        return 0

    from app.services.thumbnails import flush_thumbnails

    successes = [r for r in results if not r.get("error")]
    errors = [r for r in results if r.get("error")]

    if errors and library_id is not None:
        for err in errors:
            asset_path = err.get("asset_path", "")
            session.add(
                ProcessingError(
                    library_id=library_id,
                    scan_job_id=job_id,
                    asset_path=asset_path,
                    filename=Path(asset_path).name if asset_path else "",
                    error_type="thumbnail",
                    error_message=str(err.get("message", "缩略图生成失败")),
                )
            )
        session.commit()

    if successes:
        flush_thumbnails(session, successes)

    newly_ready = 0
    for result in successes:
        asset_id = result.get("asset_id")
        size = result.get("size")
        if not isinstance(asset_id, int) or size not in THUMBNAIL_READY_SIZES:
            continue
        sizes = ready_sizes.setdefault(asset_id, set())
        sizes.add(size)
        if asset_id not in ready_assets and all(item in sizes for item in THUMBNAIL_READY_SIZES):
            ready_assets.add(asset_id)
            newly_ready += 1
    return newly_ready


def _collect_thumbnail_results(
    futures: list[concurrent.futures.Future],
    cancel_event: threading.Event | None,
    wait: bool,
    future_contexts: dict[concurrent.futures.Future, dict] | None = None,
    wait_for_one: bool = False,
) -> list[dict]:
    results: list[dict] = []
    if wait_for_one and futures:
        done, pending_set = concurrent.futures.wait(
            list(futures),
            return_when=concurrent.futures.FIRST_COMPLETED,
        )
        for future in done:
            _check_cancelled(cancel_event)
            result = _thumbnail_future_result(future)
            if result is None and future_contexts:
                ctx = future_contexts.get(future)
                if ctx:
                    result = {
                        "error": True,
                        "asset_id": ctx["asset_id"],
                        "size": ctx["size"],
                        "asset_path": ctx["asset_path"],
                        "message": "缩略图生成异常：后台任务执行失败",
                    }
            if result:
                results.append(result)
        futures[:] = list(pending_set)
        return results

    if wait:
        for future in concurrent.futures.as_completed(list(futures)):
            _check_cancelled(cancel_event)
            result = _thumbnail_future_result(future)
            if result is None and future_contexts:
                ctx = future_contexts.get(future)
                if ctx:
                    result = {
                        "error": True,
                        "asset_id": ctx["asset_id"],
                        "size": ctx["size"],
                        "asset_path": ctx["asset_path"],
                        "message": "缩略图生成异常：后台任务执行失败",
                    }
            if result:
                results.append(result)
        futures.clear()
        return results

    pending: list[concurrent.futures.Future] = []
    for future in futures:
        if not future.done():
            pending.append(future)
            continue
        _check_cancelled(cancel_event)
        result = _thumbnail_future_result(future)
        if result is None and future_contexts:
            ctx = future_contexts.get(future)
            if ctx:
                result = {
                    "error": True,
                    "asset_id": ctx["asset_id"],
                    "size": ctx["size"],
                    "asset_path": ctx["asset_path"],
                    "message": "缩略图生成异常：后台任务执行失败",
                }
        if result:
            results.append(result)
    futures[:] = pending
    return results


def _thumbnail_future_result(future: concurrent.futures.Future) -> dict | None:
    try:
        result = future.result()
    except Exception:
        logger.warning("Thumbnail future raised unexpected exception", exc_info=True)
        return None
    return result if isinstance(result, dict) else None


def _clean_future_contexts(
    contexts: dict[concurrent.futures.Future, dict],
    kept_futures: list[concurrent.futures.Future],
) -> None:
    kept = set(kept_futures)
    for future in list(contexts):
        if future not in kept:
            del contexts[future]


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
        job.started_at = utc_now()
        job.total_estimated = None
        job.total_estimated_images = 0
        job.total_estimated_videos = 0
        job.processed_assets = 0
        job.processed_images = 0
        job.processed_videos = 0
        job.thumbnail_ready_images = 0
        session.commit()

        total = scan_library(
            session, job.library_id, job=job, generate_thumbnails=generate_thumbnails, cancel_event=cancel_event
        )
    except ScanCancelled:
        return
    except Exception as exc:  # pragma: no cover - defensive status reporting
        session.rollback()
        job.status = "failed"
        job.message = str(exc)
        job.finished_at = utc_now()
        session.add(job)
        session.commit()
        raise
    finally:
        with _cancel_lock:
            _cancel_events.pop(job_id, None)

    if job.status == "running":
        job.status = "completed"
        job.total_assets = total
        if not job.message.startswith("Indexed "):
            job.message = f"Indexed {total} media items"
        job.finished_at = utc_now()
    session.commit()
