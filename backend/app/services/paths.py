from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status


def resolve_library_path(path: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Library path must be an existing directory")
    return resolved


def safe_asset_path(library_root: str, relative_path: str) -> Path:
    root = Path(library_root).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset path is outside the library") from exc
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset file not found")
    return candidate
