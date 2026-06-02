from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, ImageOps
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


def ensure_thumbnail(session: Session, asset: Asset, size: str) -> Path:
    if size not in THUMBNAIL_SIZES:
        size = "medium"
    existing = session.exec(select(Thumbnail).where(Thumbnail.asset_id == asset.id, Thumbnail.size == size)).first()
    if existing and Path(existing.path).exists():
        return Path(existing.path)

    library = session.get(LibraryRoot, asset.library_id)
    if not library:
        raise FileNotFoundError("Library not found")
    original_path = safe_asset_path(library.path, asset.path)
    output_path = thumbnail_cache_path(asset, size)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    max_size = THUMBNAIL_SIZES[size]

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
        existing.path = str(output_path)
        existing.width = width
        existing.height = height
    else:
        session.add(Thumbnail(asset_id=asset.id or 0, size=size, path=str(output_path), width=width, height=height))
    session.commit()
    return output_path
