from __future__ import annotations

import os
import threading
from pathlib import Path

from PIL import ExifTags, Image, TiffImagePlugin
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import settings
from app.db import mark_interrupted_scan_jobs
from app.models import Asset, Folder, LibraryRoot, ScanJob, Thumbnail
from app.services.scanner import (
    active_scan_job,
    is_supported_image,
    is_supported_media,
    is_supported_video,
    refresh_folder_counts,
    run_scan_job,
    scan_library,
)
from app.services.thumbnails import bulk_generate_thumbnails, thumbnail_cache_path


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
        assert updated.processed_assets == 2


def test_active_scan_job_finds_latest_queued_or_running_job(tmp_path: Path) -> None:
    photo_root = tmp_path / "active-job"
    photo_root.mkdir()

    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Active Job", path=str(photo_root.resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)

        session.add(ScanJob(library_id=library.id or 0, status="completed", message="Done"))
        session.add(ScanJob(library_id=library.id or 0, status="queued", message="Queued"))
        session.add(ScanJob(library_id=library.id or 0, status="running", message="Running"))
        session.commit()

        active = active_scan_job(session, library.id or 0)
        assert active is not None
        assert active.message == "Running"


def test_mark_interrupted_scan_jobs_clears_startup_leftovers(tmp_path: Path) -> None:
    photo_root = tmp_path / "interrupted-job"
    photo_root.mkdir()

    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Interrupted Job", path=str(photo_root.resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)

        session.add(ScanJob(library_id=library.id or 0, status="queued", message="Queued"))
        session.add(ScanJob(library_id=library.id or 0, status="running", message="Running"))
        session.add(ScanJob(library_id=library.id or 0, status="completed", message="Done"))
        session.commit()

        mark_interrupted_scan_jobs(session)

        jobs = session.exec(select(ScanJob).order_by(ScanJob.id)).all()
        assert [job.status for job in jobs] == ["failed", "failed", "completed"]
        assert jobs[0].message == "Interrupted by server restart"
        assert jobs[1].finished_at is not None
        assert jobs[2].message == "Done"


def test_cancelled_scan_does_not_delete_unvisited_assets(tmp_path: Path) -> None:
    photo_root = tmp_path / "cancel-no-delete"
    create_photo(photo_root / "one.jpg")
    create_photo(photo_root / "two.jpg")

    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Cancel No Delete", path=str(photo_root.resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)
        assert scan_library(session, library.id or 0) == 2

        job = ScanJob(library_id=library.id or 0, status="running", message="Running")
        session.add(job)
        session.commit()
        session.refresh(job)
        cancel_event = threading.Event()
        cancel_event.set()

        assert scan_library(session, library.id or 0, job=job, cancel_event=cancel_event) == 0

        updated = session.get(ScanJob, job.id or 0)
        assert updated is not None
        assert updated.status == "cancelled"
        assert updated.message == "Scan cancelled after 0 items"
        assert {asset.path for asset in session.exec(select(Asset)).all()} == {"one.jpg", "two.jpg"}


def test_cancelled_thumbnail_generation_marks_job_cancelled(tmp_path: Path) -> None:
    class CancelBeforeThumbnails:
        def __init__(self) -> None:
            self.calls = 0

        def is_set(self) -> bool:
            self.calls += 1
            return self.calls >= 3

    photo_root = tmp_path / "cancel-thumbnails"
    create_photo(photo_root / "one.jpg")

    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Cancel Thumbnails", path=str(photo_root.resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)
        job = ScanJob(library_id=library.id or 0, status="running", message="Running")
        session.add(job)
        session.commit()
        session.refresh(job)

        total = scan_library(
            session,
            library.id or 0,
            job=job,
            generate_thumbnails=True,
            cancel_event=CancelBeforeThumbnails(),  # type: ignore[arg-type]
        )

        updated = session.get(ScanJob, job.id or 0)
        assert total == 1
        assert updated is not None
        assert updated.status == "cancelled"
        assert updated.total_assets == 1
        assert updated.message == "Indexed 1 media items (thumbnail generation cancelled)"


def test_scan_job_preserves_thumbnail_generation_message(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", (tmp_path / "data").resolve())
    try:
        photo_root = tmp_path / "thumb-job"
        create_photo(photo_root / "one.jpg")

        with make_session(tmp_path) as session:
            library = LibraryRoot(name="Thumbnail Job", path=str(photo_root.resolve()))
            session.add(library)
            session.commit()
            session.refresh(library)
            job = ScanJob(library_id=library.id or 0, status="queued", message="Queued")
            session.add(job)
            session.commit()
            session.refresh(job)

            run_scan_job(session, job.id or 0, generate_thumbnails=True)

            updated = session.get(ScanJob, job.id or 0)
            assert updated is not None
            assert updated.status == "completed"
            assert updated.total_assets == 1
            assert updated.message == "Indexed 1 media items, 2 thumbnails generated"
    finally:
        object.__setattr__(settings, "data_dir", old_data_dir)


def test_bulk_generate_thumbnails_regenerates_stale_cache(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", (tmp_path / "data").resolve())
    try:
        photo_root = tmp_path / "stale-thumbnails"
        photo_path = photo_root / "one.jpg"
        create_photo(photo_path)

        with make_session(tmp_path) as session:
            library = LibraryRoot(name="Stale Thumbnails", path=str(photo_root.resolve()))
            session.add(library)
            session.commit()
            session.refresh(library)

            scan_library(session, library.id or 0)
            asset = session.exec(select(Asset)).one()
            assert bulk_generate_thumbnails(session, [asset.id or 0], max_workers=1) == 1
            original_thumbnail = session.exec(select(Thumbnail)).one()
            original_path = Path(original_thumbnail.path)
            assert original_path.exists()

            Image.new("RGB", (128, 96), "#ef8d5b").save(photo_path)
            os.utime(photo_path, (asset.mtime + 10, asset.mtime + 10))
            scan_library(session, library.id or 0)
            updated_asset = session.exec(select(Asset)).one()
            expected_path = thumbnail_cache_path(updated_asset, "small")
            assert expected_path != original_path

            assert bulk_generate_thumbnails(session, [updated_asset.id or 0], max_workers=1) == 1
            updated_thumbnail = session.exec(select(Thumbnail)).one()
            assert updated_thumbnail.path == str(expected_path)
            assert expected_path.exists()
            assert not original_path.exists()
    finally:
        object.__setattr__(settings, "data_dir", old_data_dir)


def test_bulk_generate_thumbnails_counts_video_placeholders(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", (tmp_path / "data").resolve())
    try:
        photo_root = tmp_path / "video-thumbnails"
        photo_root.mkdir()
        (photo_root / "clip.mp4").write_bytes(b"video")

        with make_session(tmp_path) as session:
            library = LibraryRoot(name="Video Thumbnails", path=str(photo_root.resolve()))
            session.add(library)
            session.commit()
            session.refresh(library)
            folder = Folder(library_id=library.id or 0, path="", name="Video Thumbnails")
            session.add(folder)
            session.commit()
            session.refresh(folder)
            asset = Asset(
                library_id=library.id or 0,
                folder_id=folder.id or 0,
                filename="clip.mp4",
                path="clip.mp4",
                mime_type="video/mp4",
                mtime=1,
            )
            session.add(asset)
            session.commit()
            session.refresh(asset)

            assert bulk_generate_thumbnails(session, [asset.id or 0], max_workers=1) == 1
            thumbnail = session.exec(select(Thumbnail)).one()
            assert Path(thumbnail.path).exists()
            assert thumbnail.width == 320
            assert thumbnail.height == 320
    finally:
        object.__setattr__(settings, "data_dir", old_data_dir)


def test_refresh_folder_counts_uses_latest_mtime_for_cover(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Cover Library", path=str((tmp_path / "photos").resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)

        folder = Folder(library_id=library.id or 0, path="", name="Cover Library")
        session.add(folder)
        session.commit()
        session.refresh(folder)

        latest_asset = Asset(
            library_id=library.id or 0,
            folder_id=folder.id or 0,
            filename="latest.jpg",
            path="latest.jpg",
            mime_type="image/jpeg",
            mtime=200,
        )
        older_asset = Asset(
            library_id=library.id or 0,
            folder_id=folder.id or 0,
            filename="older.jpg",
            path="older.jpg",
            mime_type="image/jpeg",
            mtime=100,
        )
        session.add(latest_asset)
        session.commit()
        session.refresh(latest_asset)
        session.add(older_asset)
        session.commit()
        session.refresh(older_asset)

        refresh_folder_counts(session, library)
        session.refresh(folder)
        assert latest_asset.id is not None
        assert older_asset.id is not None
        assert older_asset.id > latest_asset.id
        assert folder.cover_asset_id == latest_asset.id

        session.delete(latest_asset)
        session.commit()
        refresh_folder_counts(session, library)
        session.refresh(folder)
        assert folder.cover_asset_id == older_asset.id

        session.delete(older_asset)
        session.commit()
        refresh_folder_counts(session, library)
        session.refresh(folder)
        assert folder.cover_asset_id is None
