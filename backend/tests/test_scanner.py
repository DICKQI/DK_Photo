from __future__ import annotations

from pathlib import Path

from PIL import ExifTags, Image, TiffImagePlugin
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Asset, Folder, LibraryRoot, ScanJob
from app.services.scanner import is_supported_image, is_supported_media, is_supported_video, run_scan_job, scan_library


EXIF_TAGS = {value: key for key, value in ExifTags.TAGS.items()}
GPS_TAGS = {value: key for key, value in ExifTags.GPSTAGS.items()}


def make_session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def create_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 48), "#5b8def").save(path)


def create_exif_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (64, 48), "#5b8def")
    exif = Image.Exif()
    exif[EXIF_TAGS["DateTimeOriginal"]] = "2024:05:12 10:30:45"
    exif[EXIF_TAGS["Make"]] = "Canon"
    exif[EXIF_TAGS["Model"]] = "EOS R6"
    exif[EXIF_TAGS["LensModel"]] = "RF 24-70mm"
    exif[EXIF_TAGS["ISOSpeedRatings"]] = 400
    exif[EXIF_TAGS["FNumber"]] = TiffImagePlugin.IFDRational(28, 10)
    exif[EXIF_TAGS["ExposureTime"]] = TiffImagePlugin.IFDRational(1, 125)
    exif[EXIF_TAGS["FocalLength"]] = TiffImagePlugin.IFDRational(50, 1)
    exif[EXIF_TAGS["GPSInfo"]] = {
        GPS_TAGS["GPSLatitudeRef"]: "N",
        GPS_TAGS["GPSLatitude"]: (
            TiffImagePlugin.IFDRational(37, 1),
            TiffImagePlugin.IFDRational(48, 1),
            TiffImagePlugin.IFDRational(30, 1),
        ),
        GPS_TAGS["GPSLongitudeRef"]: "W",
        GPS_TAGS["GPSLongitude"]: (
            TiffImagePlugin.IFDRational(122, 1),
            TiffImagePlugin.IFDRational(24, 1),
            TiffImagePlugin.IFDRational(15, 1),
        ),
    }
    image.save(path, exif=exif)


def test_supported_formats_skip_heic() -> None:
    assert is_supported_image(Path("a.jpg"))
    assert is_supported_image(Path("a.PNG"))
    assert is_supported_image(Path("a.webp"))
    assert is_supported_image(Path("a.gif"))
    assert not is_supported_image(Path("a.heic"))
    assert not is_supported_image(Path("a.mov"))
    assert is_supported_video(Path("clip.MOV"))
    assert is_supported_video(Path("clip.mp4"))
    assert is_supported_media(Path("clip.mp4"))


def test_scan_library_creates_folders_and_assets(tmp_path: Path) -> None:
    photo_root = tmp_path / "photos"
    create_photo(photo_root / "Trips" / "Lake" / "one.jpg")
    create_photo(photo_root / "Family" / "two.png")
    (photo_root / "Family" / "clip.mp4").write_bytes(b"not a real mp4 but indexed by extension")
    (photo_root / "ignore.heic").write_bytes(b"not indexed")

    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Family Photos", path=str(photo_root.resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)

        total = scan_library(session, library.id or 0)

        assert total == 3
        folders = session.exec(select(Folder)).all()
        assets = session.exec(select(Asset)).all()
        assert {folder.path for folder in folders} == {"", "Trips", "Trips/Lake", "Family"}
        assert {asset.path for asset in assets} == {"Trips/Lake/one.jpg", "Family/two.png", "Family/clip.mp4"}
        video = session.exec(select(Asset).where(Asset.filename == "clip.mp4")).one()
        assert video.mime_type == "video/mp4"
        assert video.width is None
        assert video.height is None


def test_scan_library_extracts_photo_exif_metadata(tmp_path: Path) -> None:
    photo_root = tmp_path / "photos"
    create_exif_photo(photo_root / "camera.jpg")

    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Camera Roll", path=str(photo_root.resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)

        total = scan_library(session, library.id or 0)

        assert total == 1
        asset = session.exec(select(Asset)).one()
        assert asset.captured_at is not None
        assert asset.captured_at.year == 2024
        assert asset.captured_at.month == 5
        assert asset.captured_at.day == 12
        assert asset.camera_make == "Canon"
        assert asset.camera_model == "EOS R6"
        assert asset.lens_model == "RF 24-70mm"
        assert asset.iso == 400
        assert asset.aperture == "f/2.8"
        assert asset.exposure_time == "1/125 s"
        assert asset.focal_length == "50 mm"
        assert asset.latitude == 37.8083333
        assert asset.longitude == -122.4041667


def test_scan_job_reports_indexed_media_items(tmp_path: Path) -> None:
    photo_root = tmp_path / "job-media"
    create_photo(photo_root / "one.jpg")
    (photo_root / "clip.mp4").write_bytes(b"video")

    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Mixed Media", path=str(photo_root.resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)
        job = ScanJob(library_id=library.id or 0, status="queued", message="Queued")
        session.add(job)
        session.commit()
        session.refresh(job)

        run_scan_job(session, job.id or 0)

        updated = session.get(ScanJob, job.id or 0)
        assert updated is not None
        assert updated.status == "completed"
        assert updated.total_assets == 2
        assert updated.message == "Indexed 2 media items"
