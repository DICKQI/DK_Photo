from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from PIL import ExifTags, Image, TiffImagePlugin
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import settings
from app.db import disable_legacy_docker_photos_root_library, mark_interrupted_scan_jobs
from app.models import Asset, Folder, LibraryRoot, ProcessingError, ScanJob, Thumbnail
from app.services.scanner import (
    active_scan_job,
    get_image_metadata,
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


def create_orientation_exif_photo(path: Path) -> None:
    """Write a JPEG with Orientation=6 (90° CW), GPS, LensModel, and full EXIF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (160, 120), "#5b8def")
    exif = Image.Exif()
    exif[EXIF_TAGS["Orientation"]] = 6
    exif[EXIF_TAGS["DateTimeOriginal"]] = "2024:05:12 10:30:45"
    exif[EXIF_TAGS["DateTimeDigitized"]] = "2024:05:12 10:30:44"
    exif[EXIF_TAGS["Make"]] = "Canon"
    exif[EXIF_TAGS["Model"]] = "EOS R6"
    exif[EXIF_TAGS["LensModel"]] = "RF24-105mm F4 L IS USM"
    exif[EXIF_TAGS["ISOSpeedRatings"]] = 800
    exif[EXIF_TAGS["FNumber"]] = TiffImagePlugin.IFDRational(40, 10)
    exif[EXIF_TAGS["ExposureTime"]] = TiffImagePlugin.IFDRational(1, 250)
    exif[EXIF_TAGS["FocalLength"]] = TiffImagePlugin.IFDRational(105, 1)
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


def test_scan_library_skips_docker_photos_mount_root(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Docker mount root", path="/photos")
        session.add(library)
        session.commit()
        session.refresh(library)

        total = scan_library(session, library.id or 0)

        assert total == 0
        assert session.exec(select(Folder)).all() == []
        assert session.exec(select(Asset)).all() == []


def test_legacy_empty_docker_photos_library_is_disabled(tmp_path: Path) -> None:
    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Family Photos", path="/photos", is_enabled=True)
        session.add(library)
        session.commit()
        session.refresh(library)

        disable_legacy_docker_photos_root_library(session)
        session.refresh(library)

        assert library.is_enabled is False


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
        assert updated.total_estimated is None
        assert updated.total_estimated_images == 0
        assert updated.total_estimated_videos == 0
        assert updated.message == "Indexed 2 media items"
        assert updated.processed_assets == 2
        assert updated.processed_images == 1
        assert updated.processed_videos == 1
        assert updated.thumbnail_ready_images == 0


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
        assert updated.processed_assets == 1
        assert updated.processed_images == 1
        assert updated.processed_videos == 0
        assert updated.message == "Scan cancelled after 1 items"


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
            assert updated.total_estimated_images == 0
            assert updated.processed_images == 1
            assert updated.thumbnail_ready_images == 1
            assert updated.message == "Indexed 1 media items, 1 thumbnail-ready images"
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


def test_pipeline_generates_thumbnails_for_images(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", (tmp_path / "data").resolve())
    try:
        photo_root = tmp_path / "pipeline-thumbs"
        for i in range(5):
            create_photo(photo_root / f"img{i}.jpg")

        with make_session(tmp_path) as session:
            library = LibraryRoot(name="Pipeline Thumbs", path=str(photo_root.resolve()))
            session.add(library)
            session.commit()
            session.refresh(library)

            total = scan_library(session, library.id or 0, generate_thumbnails=True)
            assert total == 5

            thumbnails = session.exec(select(Thumbnail)).all()
            assert len(thumbnails) == 10  # 5 images * 2 sizes (small + medium)
            for thumb in thumbnails:
                assert Path(thumb.path).exists()

            sizes = {thumb.size for thumb in thumbnails}
            assert sizes == {"small", "medium"}
    finally:
        object.__setattr__(settings, "data_dir", old_data_dir)


def test_pipeline_skips_unchanged_images(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", (tmp_path / "data").resolve())
    try:
        photo_root = tmp_path / "pipeline-skip"
        create_photo(photo_root / "one.jpg")

        with make_session(tmp_path) as session:
            library = LibraryRoot(name="Pipeline Skip", path=str(photo_root.resolve()))
            session.add(library)
            session.commit()
            session.refresh(library)

            scan_library(session, library.id or 0, generate_thumbnails=True)
            first_thumbnails = session.exec(select(Thumbnail)).all()
            assert len(first_thumbnails) == 2

            job = ScanJob(library_id=library.id or 0, status="running", message="Rescan")
            session.add(job)
            session.commit()
            session.refresh(job)

            scan_library(session, library.id or 0, job=job, generate_thumbnails=True)
            second_thumbnails = session.exec(select(Thumbnail)).all()
            assert len(second_thumbnails) == 2

            assert {t.id for t in first_thumbnails} == {t.id for t in second_thumbnails}
            updated = session.get(ScanJob, job.id or 0)
            assert updated is not None
            assert updated.processed_images == 1
            assert updated.thumbnail_ready_images == 1
    finally:
        object.__setattr__(settings, "data_dir", old_data_dir)


def test_pipeline_regenerates_missing_thumbnail_for_unchanged_image(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", (tmp_path / "data").resolve())
    try:
        photo_root = tmp_path / "pipeline-repair"
        create_photo(photo_root / "one.jpg")

        with make_session(tmp_path) as session:
            library = LibraryRoot(name="Pipeline Repair", path=str(photo_root.resolve()))
            session.add(library)
            session.commit()
            session.refresh(library)

            scan_library(session, library.id or 0, generate_thumbnails=True)
            thumbnail = session.exec(select(Thumbnail).where(Thumbnail.size == "small")).one()
            missing_path = Path(thumbnail.path)
            missing_path.unlink(missing_ok=True)
            session.delete(thumbnail)
            session.commit()

            scan_library(session, library.id or 0, generate_thumbnails=True)

            thumbnails = session.exec(select(Thumbnail)).all()
            assert len(thumbnails) == 2
            assert all(Path(item.path).exists() for item in thumbnails)
    finally:
        object.__setattr__(settings, "data_dir", old_data_dir)


def test_pipeline_no_thumbnails_when_disabled(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", (tmp_path / "data").resolve())
    try:
        photo_root = tmp_path / "pipeline-off"
        create_photo(photo_root / "one.jpg")
        create_photo(photo_root / "two.jpg")

        with make_session(tmp_path) as session:
            library = LibraryRoot(name="Pipeline Off", path=str(photo_root.resolve()))
            session.add(library)
            session.commit()
            session.refresh(library)

            total = scan_library(session, library.id or 0, generate_thumbnails=False)
            assert total == 2
            assert session.exec(select(Thumbnail)).all() == []
    finally:
        object.__setattr__(settings, "data_dir", old_data_dir)


def test_scan_library_records_metadata_error_for_corrupt_image(tmp_path: Path) -> None:
    photo_root = tmp_path / "corrupt-metadata"
    bad_photo = photo_root / "bad.jpg"
    bad_photo.parent.mkdir(parents=True, exist_ok=True)
    bad_photo.write_bytes(b"not a real jpeg")

    with make_session(tmp_path) as session:
        library = LibraryRoot(name="Corrupt Metadata", path=str(photo_root.resolve()))
        session.add(library)
        session.commit()
        session.refresh(library)

        total = scan_library(session, library.id or 0)

        assert total == 1
        asset = session.exec(select(Asset)).one()
        assert asset.width is None
        error = session.exec(select(ProcessingError)).one()
        assert error.error_type == "metadata"
        assert error.asset_path == "bad.jpg"


def test_pipeline_empty_library_no_thumbnails(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    object.__setattr__(settings, "data_dir", (tmp_path / "data").resolve())
    try:
        photo_root = tmp_path / "pipeline-empty"
        photo_root.mkdir()
        (photo_root / "readme.txt").write_text("hello")

        with make_session(tmp_path) as session:
            library = LibraryRoot(name="Pipeline Empty", path=str(photo_root.resolve()))
            session.add(library)
            session.commit()
            session.refresh(library)

            total = scan_library(session, library.id or 0, generate_thumbnails=True)
            assert total == 0
            assert session.exec(select(Thumbnail)).all() == []
    finally:
        object.__setattr__(settings, "data_dir", old_data_dir)


def test_pillow_metadata_extracts_orientation_gps_and_lens(tmp_path: Path) -> None:
    """Verify Pillow-based metadata extraction covers orientation, GPS, lens, and core EXIF fields."""
    photo_path = tmp_path / "parity.jpg"
    create_orientation_exif_photo(photo_path)

    meta = get_image_metadata(photo_path)

    # Core metadata fields
    assert meta["camera_make"] == "Canon"
    assert meta["camera_model"] == "EOS R6"
    assert meta["lens_model"] == "RF24-105mm F4 L IS USM"
    assert meta["iso"] == 800
    assert meta["aperture"] == "f/4"
    assert meta["exposure_time"] == "1/250 s"
    assert meta["focal_length"] == "105 mm"

    # Captured datetime
    assert meta["captured_at"] is not None
    assert meta["captured_at"].year == 2024
    assert meta["captured_at"].month == 5
    assert meta["captured_at"].day == 12

    # GPS coordinates
    assert meta["latitude"] == pytest.approx(37.8083333, abs=1e-6)
    assert meta["longitude"] == pytest.approx(-122.4041667, abs=1e-6)

    # Orientation: 6 means 90° CW, so width/height should swap
    assert meta["width"] == 120   # original height
    assert meta["height"] == 160  # original width


def test_exif_metadata_uses_pillow_only_path(tmp_path: Path) -> None:
    """Ensure get_image_metadata works through the Pillow-only path."""
    photo_path = tmp_path / "pillow_only.jpg"
    create_orientation_exif_photo(photo_path)

    meta = get_image_metadata(photo_path)

    assert meta["camera_make"] == "Canon"
    assert meta["camera_model"] == "EOS R6"
    assert meta["lens_model"] == "RF24-105mm F4 L IS USM"
    assert meta["iso"] == 800
    assert meta["aperture"] == "f/4"
    assert meta["width"] == 120
    assert meta["height"] == 160
    assert meta["latitude"] == pytest.approx(37.8083333, abs=1e-6)
    assert meta["longitude"] == pytest.approx(-122.4041667, abs=1e-6)
