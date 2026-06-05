from __future__ import annotations

from pathlib import Path

from app.services.filesystem import COUNT_UNKNOWN, list_children, list_roots


def test_list_roots_returns_platform_metadata() -> None:
    roots = list_roots()
    assert roots.platform
    assert roots.separator
    assert roots.roots
    assert all(entry.kind for entry in roots.roots)
    assert any(entry.kind in {"drive", "favorite"} for entry in roots.roots)


def test_list_children_returns_only_directories(tmp_path: Path) -> None:
    (tmp_path / "folder").mkdir()
    (tmp_path / "photo.jpg").write_bytes(b"ignored")
    (tmp_path / "clip.mp4").write_bytes(b"ignored")
    (tmp_path / "skip.heic").write_bytes(b"ignored")
    (tmp_path / "notes.txt").write_text("ignored")

    children = list_children(str(tmp_path))

    assert children.path == str(tmp_path.resolve())
    assert children.child_folder_count == 1
    assert children.image_count == 1
    assert children.media_count == 2
    assert {entry.name for entry in children.entries} == {"folder"}


def test_list_children_does_not_precount_child_directories(tmp_path: Path) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "nested").mkdir()
    (folder / "photo.jpg").write_bytes(b"ignored")

    children = list_children(str(tmp_path))

    assert children.child_folder_count == 1
    assert children.image_count == 0
    assert children.media_count == 0
    entry = children.entries[0]
    assert entry.name == "folder"
    assert entry.child_folder_count == COUNT_UNKNOWN
    assert entry.image_count == COUNT_UNKNOWN
    assert entry.media_count == COUNT_UNKNOWN
