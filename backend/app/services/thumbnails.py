from __future__ import annotations

import concurrent.futures
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps
from sqlmodel import Session, select

from app.config import settings
from app.models import Asset, LibraryRoot, Thumbnail
from app.services.paths import safe_asset_path


THUMBNAIL_SIZES: dict[str, tuple[int, int]] = {
    "small": (320, 320),
    "medium": (720, 720),
    "large": (1440, 1440),
}

DEFAULT_THUMB_WORKERS = 4


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

    if asset.mime_type.startswith("video/"):
        width, height = write_video_placeholder(output_path, max_size)
        if existing:
            _delete_old_thumbnail(existing, output_path)
            existing.path = str(output_path)
            existing.width = width
            existing.height = height
        else:
            session.add(Thumbnail(asset_id=asset.id or 0, size=size, path=str(output_path), width=width, height=height))
        session.commit()
        return output_path

    with Image.open(original_path) as image:
        image = ImageOps.exif_transpose(image)
        if getattr(image, "is_animated", False):
            image.seek(0)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGB")
        image.save(output_path, "WEBP", quality=82, method=4)
        width, height = image.size

    if existing:
        _delete_old_thumbnail(existing, output_path)
        existing.path = str(output_path)
        existing.width = width
        existing.height = height
    else:
        session.add(Thumbnail(asset_id=asset.id or 0, size=size, path=str(output_path), width=width, height=height))
    session.commit()
    return output_path


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
    image.save(output_path, "WEBP", quality=82, method=4)
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
            image.save(output_path, "WEBP", quality=82, method=4)
            return image.size
    except Exception:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def bulk_generate_thumbnails(
    session: Session,
    asset_ids: list[int],
    size: str = "small",
    max_workers: int = DEFAULT_THUMB_WORKERS,
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

    results: list[tuple[Asset, Path, int, int]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item: dict[concurrent.futures.Future, tuple[Asset, Path, Path]] = {
            executor.submit(_generate_thumbnail_file, item[1], item[2], max_size): item
            for item in work_items
        }
        for future in concurrent.futures.as_completed(future_to_item):
            asset_item = future_to_item[future]
            try:
                dims = future.result()
                if dims:
                    results.append((asset_item[0], asset_item[2], dims[0], dims[1]))
            except Exception:
                pass

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

    session.commit()
    return generated_count + len(results)
