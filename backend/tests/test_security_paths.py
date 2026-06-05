from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.paths import is_docker_photos_root, resolve_library_path, safe_asset_path


def test_docker_photos_root_is_not_a_library_path() -> None:
    assert is_docker_photos_root("/photos")
    assert is_docker_photos_root("/photos/")
    assert not is_docker_photos_root("/photos/travel")

    with pytest.raises(HTTPException):
        resolve_library_path("/photos")


def test_safe_asset_path_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "photos"
    root.mkdir()
    outside = tmp_path / "secret.jpg"
    outside.write_bytes(b"secret")

    with pytest.raises(HTTPException):
        safe_asset_path(str(root), "../secret.jpg")


def test_safe_asset_path_allows_inside_file(tmp_path: Path) -> None:
    root = tmp_path / "photos"
    image = root / "a.jpg"
    image.parent.mkdir()
    image.write_bytes(b"image")

    assert safe_asset_path(str(root), "a.jpg") == image.resolve()
