from __future__ import annotations

import concurrent.futures
import hashlib
import os
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from app.config import settings
from app.models import Asset, LibraryRoot, Thumbnail
from app.services.paths import safe_asset_path


THUMBNAIL_SIZES: dict[str, tuple[int, int]] = {
    "small": (320, 320),
    "medium": (720, 720),
    "large": (1440, 1440),
}

DEFAULT_THUMB_WORKERS = max(2, (os.cpu_count() or 4) // 2)


def thumbnail_cache_path(asset: Asset, size: str) -> Path:
    digest = hashlib.sha1(f"{asset.id}:{asset.path}:{asset.mtime}:{size}".encode("utf-8")).hexdigest()
    return settings.thumbnail_dir / digest[:2] / f"{digest}.webp"


def _delete_old_thumbnail(existing: Thumbnail, new_path: Path) -> None:
    old = Path(existing.path)
    if old != new_path and old.exists():
        old.unlink(missing_ok=True)


def ensure_thumbnail(session: Session, asset: Asset, size: str) -> Path:
    if size not in THUMBNAIL_SIZES:
        size = "medium"
    asset_id = asset.id or 0
    asset_mime_type = asset.mime_type
    existing = session.exec(select(Thumbnail).where(Thumbnail.asset_id == asset.id, Thumbnail.size == size)).first()
    expected_path = thumbnail_cache_path(asset, size)

    if existing and existing.path == str(expected_path) and Path(existing.path).exists():
        return expected_path

    library = session.get(LibraryRoot, asset.library_id)
    if not library:
        raise FileNotFoundError("Library not found")
    original_path = safe_asset_path(library.path, asset.path)
    output_path = expected_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    max_size = THUMBNAIL_SIZES[size]
    existing_id = existing.id if existing else None
    session.rollback()

    if asset_mime_type.startswith("video/"):
        width, height = write_video_placeholder(output_path, max_size)
        _save_thumbnail_record(session, asset_id, size, output_path, width, height, existing_id)
        return output_path

    with Image.open(original_path) as image:
        image = ImageOps.exif_transpose(image)
        if getattr(image, "is_animated", False):
            image.seek(0)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        image.save(output_path, "WEBP", quality=82, method=3)
        width, height = image.size

    _save_thumbnail_record(session, asset_id, size, output_path, width, height, existing_id)
    return output_path


def _save_thumbnail_record(
    session: Session,
    asset_id: int,
    size: str,
    output_path: Path,
    width: int,
    height: int,
    existing_id: int | None = None,
) -> None:
    existing = session.get(Thumbnail, existing_id) if existing_id else None
    if not existing:
        existing = session.exec(select(Thumbnail).where(Thumbnail.asset_id == asset_id, Thumbnail.size == size)).first()
    if existing:
        _delete_old_thumbnail(existing, output_path)
        existing.path = str(output_path)
        existing.width = width
        existing.height = height
    else:
        session.add(Thumbnail(asset_id=asset_id, size=size, path=str(output_path), width=width, height=height))
    try:
        session.commit()
    except OperationalError:
        session.rollback()
        if output_path.exists():
            return
        raise


def write_video_placeholder(output_path: Path, max_size: tuple[int, int]) -> tuple[int, int]:
    width, height = max_size
    image = Image.new("RGB", (width, height), "#172033")
    draw = ImageDraw.Draw(image)
    accent = "#7aa7ff"
    shadow = "#0d111a"
    triangle_size = max(54, min(width, height) // 5)
    center_x = width // 2
    center_y = height // 2
    points = [
        (center_x - triangle_size // 3, center_y - triangle_size // 2),
        (center_x - triangle_size // 3, center_y + triangle_size // 2),
        (center_x + triangle_size // 2, center_y),
    ]
    draw.rounded_rectangle(
        [
            center_x - triangle_size,
            center_y - triangle_size,
            center_x + triangle_size,
            center_y + triangle_size,
        ],
        radius=max(18, triangle_size // 3),
        fill=shadow,
        outline="#334155",
        width=max(2, triangle_size // 18),
    )
    draw.polygon(points, fill=accent)
    image.save(output_path, "WEBP", quality=82, method=3)
    return image.size


def _generate_thumbnail_file(
    original_path: Path, output_path: Path, max_size: tuple[int, int]
) -> tuple[int, int] | None:
    try:
        with Image.open(original_path) as image:
            image = ImageOps.exif_transpose(image)
            if getattr(image, "is_animated", False):
                image.seek(0)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            image.save(output_path, "WEBP", quality=82, method=3)
            return image.size
    except Exception:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _save_thumbnail_results(
    session: Session,
    results: list[tuple[Asset, Path, int, int]],
    size: str,
) -> int:
    saved = 0
    for asset, output_path, width, height in results:
        existing = session.exec(
            select(Thumbnail).where(Thumbnail.asset_id == asset.id, Thumbnail.size == size)
        ).first()
        if existing:
            _delete_old_thumbnail(existing, output_path)
            existing.path = str(output_path)
            existing.width = width
            existing.height = height
        else:
            session.add(
                Thumbnail(
                    asset_id=asset.id or 0,
                    size=size,
                    path=str(output_path),
                    width=width,
                    height=height,
                )
            )
        saved += 1
    session.commit()
    return saved


def bulk_generate_thumbnails(
    session: Session,
    asset_ids: list[int],
    size: str = "small",
    max_workers: int = DEFAULT_THUMB_WORKERS,
    cancel_event: threading.Event | None = None,
) -> int:
    if size not in THUMBNAIL_SIZES:
        size = "small"
    if not asset_ids:
        return 0
    asset_ids = list(dict.fromkeys(asset_ids))
    max_workers = max(1, max_workers)

    max_size = THUMBNAIL_SIZES[size]

    assets = session.exec(select(Asset).where(Asset.id.in_(asset_ids))).all()  # type: ignore[attr-defined]

    existing_thumbnails = session.exec(
        select(Thumbnail).where(
            Thumbnail.asset_id.in_(asset_ids),  # type: ignore[attr-defined]
            Thumbnail.size == size,
        )
    ).all()
    existing_by_asset_id = {thumbnail.asset_id: thumbnail for thumbnail in existing_thumbnails}

    work_items: list[tuple[Asset, Path, Path]] = []
    generated_count = 0
    for asset in assets:
        asset_id = asset.id or 0
        output_path = thumbnail_cache_path(asset, size)
        existing = existing_by_asset_id.get(asset_id)
        if existing and existing.path == str(output_path) and output_path.exists():
            continue
        library = session.get(LibraryRoot, asset.library_id)
        if not library:
            continue
        original_path = safe_asset_path(library.path, asset.path)
        if not original_path.exists():
            continue
        if asset.mime_type.startswith("video/"):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            width, height = write_video_placeholder(output_path, max_size)
            if existing:
                _delete_old_thumbnail(existing, output_path)
                existing.path = str(output_path)
                existing.width = width
                existing.height = height
            else:
                session.add(
                    Thumbnail(
                        asset_id=asset_id,
                        size=size,
                        path=str(output_path),
                        width=width,
                        height=height,
                    )
                )
            generated_count += 1
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            work_items.append((asset, original_path, output_path))

    if not work_items:
        session.commit()
        return generated_count

    from app.services.scanner import ScanCancelled

    results: list[tuple[Asset, Path, int, int]] = []
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    cancelled = False
    try:
        future_to_item: dict[concurrent.futures.Future, tuple[Asset, Path, Path]] = {
            executor.submit(_generate_thumbnail_file, item[1], item[2], max_size): item
            for item in work_items
        }
        for future in concurrent.futures.as_completed(future_to_item):
            if cancel_event and cancel_event.is_set():
                cancelled = True
                _save_thumbnail_results(session, results, size)
                raise ScanCancelled

            asset_item = future_to_item[future]
            try:
                dims = future.result()
                if dims:
                    results.append((asset_item[0], asset_item[2], dims[0], dims[1]))
            except Exception:
                pass

            if cancel_event and cancel_event.is_set():
                cancelled = True
                _save_thumbnail_results(session, results, size)
                raise ScanCancelled
    finally:
        executor.shutdown(wait=not cancelled, cancel_futures=cancelled)

    saved = _save_thumbnail_results(session, results, size)
    return generated_count + saved


def _thumbnail_hash_path(asset_id: int, asset_path: str, mtime: float, size: str) -> Path:
    digest = hashlib.sha1(f"{asset_id}:{asset_path}:{mtime}:{size}".encode("utf-8")).hexdigest()
    return settings.thumbnail_dir / digest[:2] / f"{digest}.webp"


def generate_thumbnail_disk_only(
    asset_id: int,
    library_path: str,
    asset_path: str,
    mtime: float,
    mime_type: str,
    size: str,
) -> dict | None:
    if size not in THUMBNAIL_SIZES:
        return None
    max_size = THUMBNAIL_SIZES[size]
    output_path = _thumbnail_hash_path(asset_id, asset_path, mtime, size)
    if output_path.exists():
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if mime_type.startswith("video/"):
        width, height = write_video_placeholder(output_path, max_size)
    else:
        original_path = safe_asset_path(library_path, asset_path)
        if not original_path.exists():
            return None
        dims = _generate_thumbnail_file(original_path, output_path, max_size)
        if dims is None:
            return None
        width, height = dims

    return {
        "asset_id": asset_id,
        "size": size,
        "path": str(output_path),
        "width": width,
        "height": height,
    }


def flush_thumbnails(session: Session, results: list[dict]) -> None:
    for entry in results:
        existing = session.exec(
            select(Thumbnail).where(
                Thumbnail.asset_id == entry["asset_id"],
                Thumbnail.size == entry["size"],
            )
        ).first()
        new_path = Path(entry["path"])
        if existing:
            _delete_old_thumbnail(existing, new_path)
            existing.path = entry["path"]
            existing.width = entry["width"]
            existing.height = entry["height"]
        else:
            session.add(
                Thumbnail(
                    asset_id=entry["asset_id"],
                    size=entry["size"],
                    path=entry["path"],
                    width=entry["width"],
                    height=entry["height"],
                )
            )
    session.commit()
