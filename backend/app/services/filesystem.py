from __future__ import annotations

import os
import platform
from pathlib import Path

from app.schemas import FilesystemChildren, FilesystemEntry, FilesystemRoots


def current_platform() -> str:
    return "windows" if os.name == "nt" else platform.system().lower() or "linux"


def list_roots() -> FilesystemRoots:
    if os.name == "nt":
        roots = []
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            root = Path(f"{letter}:\\")
            if root.exists():
                roots.append(FilesystemEntry(name=f"{letter}:\\", path=str(root), is_root=True))
        return FilesystemRoots(platform=current_platform(), separator=os.sep, roots=roots)
    return FilesystemRoots(
        platform=current_platform(),
        separator=os.sep,
        roots=[FilesystemEntry(name="/", path="/", is_root=True)],
    )


def list_children(path: str) -> FilesystemChildren:
    current = Path(path).expanduser().resolve()
    parent = current.parent if current.parent != current else None
    entries: list[FilesystemEntry] = []
    try:
        children = sorted(current.iterdir(), key=lambda item: item.name.lower())
    except OSError as exc:
        return FilesystemChildren(
            platform=current_platform(),
            separator=os.sep,
            path=str(current),
            parent_path=str(parent) if parent else None,
            entries=[FilesystemEntry(name=str(current), path=str(current), is_accessible=False, error=str(exc))],
        )

    for child in children:
        try:
            is_dir = child.is_dir()
        except OSError as exc:
            entries.append(FilesystemEntry(name=child.name, path=str(child), is_accessible=False, error=str(exc)))
            continue
        if not is_dir:
            continue
        try:
            child.iterdir()
            entries.append(FilesystemEntry(name=child.name, path=str(child)))
        except OSError as exc:
            entries.append(FilesystemEntry(name=child.name, path=str(child), is_accessible=False, error=str(exc)))

    return FilesystemChildren(
        platform=current_platform(),
        separator=os.sep,
        path=str(current),
        parent_path=str(parent) if parent else None,
        entries=entries,
    )
