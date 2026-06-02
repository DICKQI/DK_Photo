from __future__ import annotations

from pathlib import Path

from app.services.filesystem import list_children, list_roots


def test_list_roots_returns_platform_metadata() -> None:
    roots = list_roots()
    assert roots.platform
    assert roots.separator
    assert roots.roots


def test_list_children_returns_only_directories(tmp_path: Path) -> None:
    (tmp_path / "folder").mkdir()
    (tmp_path / "photo.jpg").write_bytes(b"ignored")

    children = list_children(str(tmp_path))

    assert children.path == str(tmp_path.resolve())
    assert {entry.name for entry in children.entries} == {"folder"}
