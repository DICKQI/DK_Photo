from __future__ import annotations

from pathlib import Path

from PIL import Image
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Asset, Folder, LibraryRoot
from app.services.scanner import is_supported_image, scan_library


def make_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def create_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), "#5b8def").save(path)


def test_supported_formats_skip_heic() -> None:
    assert is_supported_image(Path("a.jpg"))
    assert is_supported_image(Path("a.PNG"))
    assert is_supported_image(Path("a.webp"))
    assert is_supported_image(Path("a.gif"))
    assert not is_supported_image(Path("a.heic"))
    assert not is_supported_image(Path("a.mov"))


def test_scan_library_creates_folders_and_assets(tmp_path: Path) -> None:
    photo_root = tmp_path / "photos"
    create_photo(photo_root / "Trips" / "Lake" / "one.jpg")
    create_photo(photo_root / "Family" / "two.png")
    (photo_root / "ignore.heic").write_bytes(b"not indexed")

    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Family Photos", path=str(photo_root.resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)

        total = scan_library(session, library.id or 0)

        assert total == 2
        folders = session.exec(select(Folder)).all()
        assets = session.exec(select(Asset)).all()
        assert {folder.path for folder in folders} == {"", "Trips", "Trips/Lake", "Family"}
        assert {asset.path for asset in assets} == {"Trips/Lake/one.jpg", "Family/two.png"}
