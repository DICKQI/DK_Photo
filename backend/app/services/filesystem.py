from __future__ import annotations

import os
import platform
import string
from pathlib import Path

from app.config import settings
from app.schemas import FilesystemChildren, FilesystemEntry, FilesystemRoots
from app.services.scanner import is_supported_image, is_supported_media


COUNT_UNKNOWN = -1


def current_platform() -> str:
    return "windows" if os.name == "nt" else platform.system().lower() or "linux"


def _entry(
    path: Path,
    name: str | None = None,
    *,
    kind: str = "folder",
    group: str | None = None,
    is_root: bool = False,
) -> FilesystemEntry | None:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        return None
    if not resolved.exists() or not resolved.is_dir():
        return None
    return FilesystemEntry(
        name=name or resolved.name or str(resolved),
        path=str(resolved),
        is_root=is_root,
        kind=kind,
        group=group,
        child_folder_count=COUNT_UNKNOWN,
        image_count=COUNT_UNKNOWN,
        media_count=COUNT_UNKNOWN,
    )


def _display_path(path: Path) -> str:
    try:
        return str(path.expanduser().resolve())
    except OSError:
        return str(path)


def _add_unique(entries: list[FilesystemEntry], entry: FilesystemEntry | None) -> None:
    if not entry:
        return
    normalized = os.path.normcase(entry.path)
    if all(os.path.normcase(item.path) != normalized for item in entries):
        entries.append(entry)


def _directory_counts(path: Path) -> tuple[int, int, int]:
    child_folder_count = 0
    image_count = 0
    media_count = 0
    try:
        for child in path.iterdir():
            try:
                if child.is_dir():
                    child_folder_count += 1
                elif child.is_file() and is_supported_media(child):
                    media_count += 1
                    if is_supported_image(child):
                        image_count += 1
            except OSError:
                continue
    except OSError:
        return 0, 0, 0
    return child_folder_count, image_count, media_count


def _entry_without_counts(
    path: Path,
    *,
    name: str | None = None,
    is_accessible: bool = True,
    error: str | None = None,
) -> FilesystemEntry:
    count = COUNT_UNKNOWN if is_accessible else 0
    return FilesystemEntry(
        name=name or path.name or str(path),
        path=_display_path(path),
        is_accessible=is_accessible,
        error=error,
        child_folder_count=count,
        image_count=count,
        media_count=count,
    )


def _recommended_locations() -> list[FilesystemEntry]:
    entries: list[FilesystemEntry] = []
    home = Path.home()

    if settings.default_library_path:
        _add_unique(
            entries,
            _entry(
                Path(settings.default_library_path),
                "Configured Photos",
                kind="favorite",
                group="Recommended",
            ),
        )

    user = os.environ.get("USERNAME") or os.environ.get("USER") or "Home"
    for candidate, name, group in [
        (home / "Pictures", "Pictures", "Recommended"),
        (home / "Photos", "Photos", "Recommended"),
        (home / "OneDrive" / "Pictures", "OneDrive Pictures", "Recommended"),
        (home / "iCloud Photos", "iCloud Photos", "Recommended"),
        (home, f"{user} Home", "Advanced"),
    ]:
        _add_unique(entries, _entry(candidate, name, kind="favorite", group=group))

    if os.name != "nt":
        for candidate, name, group in [
            (Path("/photos"), "Docker /photos mount root", "Recommended"),
            (Path("/mnt"), "/mnt", "Mount points"),
            (Path("/media"), "/media", "Mount points"),
        ]:
            _add_unique(entries, _entry(candidate, name, kind="favorite", group=group))

    return entries


def _system_roots() -> list[FilesystemEntry]:
    if os.name == "nt":
        roots: list[FilesystemEntry] = []
        for letter in _windows_drive_letters():
            roots.append(_windows_drive_entry(letter))
        return roots
    root_entry = _entry(Path("/"), "/", kind="drive", group="System", is_root=True)
    return [root_entry] if root_entry else []


def _windows_drive_entry(letter: str) -> FilesystemEntry:
    path = f"{letter}:\\"
    return FilesystemEntry(
        name=path,
        path=path,
        is_root=True,
        kind="drive",
        group="Drives",
        child_folder_count=COUNT_UNKNOWN,
        image_count=COUNT_UNKNOWN,
        media_count=COUNT_UNKNOWN,
    )


def _windows_drive_letters() -> list[str]:
    try:
        import ctypes

        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return list(string.ascii_uppercase)

    if not bitmask:
        return []
    return [letter for index, letter in enumerate(string.ascii_uppercase) if bitmask & (1 << index)]


def list_roots() -> FilesystemRoots:
    roots: list[FilesystemEntry] = []
    for entry in [*_recommended_locations(), *_system_roots()]:
        _add_unique(roots, entry)
    return FilesystemRoots(platform=current_platform(), separator=os.sep, roots=roots)


def list_children(path: str) -> FilesystemChildren:
    current = Path(path).expanduser().resolve()
    parent = current.parent if current.parent != current else None
    entries: list[FilesystemEntry] = []
    current_child_folder_count = 0
    current_image_count = 0
    current_media_count = 0
    try:
        children = sorted(current.iterdir(), key=lambda item: item.name.lower())
    except OSError as exc:
        return FilesystemChildren(
            platform=current_platform(),
            separator=os.sep,
            path=str(current),
            parent_path=str(parent) if parent else None,
            entries=[
                FilesystemEntry(
                    name=str(current),
                    path=str(current),
                    is_accessible=False,
                    error=str(exc),
                    kind="error",
                )
            ],
        )

    for child in children:
        try:
            is_dir = child.is_dir()
        except OSError as exc:
            entries.append(_entry_without_counts(child, name=child.name, is_accessible=False, error=str(exc)))
            continue
        if is_dir:
            current_child_folder_count += 1
        elif is_supported_media(child):
            current_media_count += 1
            if is_supported_image(child):
                current_image_count += 1
            continue
        else:
            continue
        try:
            entries.append(_entry_without_counts(child, name=child.name))
        except OSError as exc:
            entries.append(_entry_without_counts(child, name=child.name, is_accessible=False, error=str(exc)))

    return FilesystemChildren(
        platform=current_platform(),
        separator=os.sep,
        path=str(current),
        parent_path=str(parent) if parent else None,
        entries=entries,
        child_folder_count=current_child_folder_count,
        image_count=current_image_count,
        media_count=current_media_count,
    )
