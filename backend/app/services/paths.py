from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status


def is_docker_photos_root(path: str | Path) -> bool:
    normalized = str(path).replace("\\", "/").rstrip("/")
    if normalized == "/photos":
        return True
    try:
        resolved = Path(path).expanduser().resolve()
    except OSError:
        return False
    return resolved.as_posix().rstrip("/") == "/photos"


def resolve_library_path(path: str) -> Path:
    try:
        resolved = Path(path).expanduser().resolve()
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Library path is not accessible") from exc
    if is_docker_photos_root(path) or is_docker_photos_root(resolved):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="/photos is only the Docker mount root. Choose a mounted subdirectory such as /photos/travel.",
        )
    try:
        is_existing_directory = resolved.exists() and resolved.is_dir()
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Library path is not accessible") from exc
    if not is_existing_directory:
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
