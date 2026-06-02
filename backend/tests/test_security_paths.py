from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.paths import safe_asset_path


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
