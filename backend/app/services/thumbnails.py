from __future__ import annotations

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
