from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import settings
from app.models import Asset, Folder, LibraryRoot, ScanJob, User, utc_now
from app.security import hash_password
from app.services.paths import is_docker_photos_root


connect_args = {"check_same_thread": False, "timeout": 30}
engine = create_engine(settings.database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-65536")
        cursor.execute("PRAGMA mmap_size=268435456")
        cursor.execute("PRAGMA temp_store=MEMORY")
    finally:
        cursor.close()


def create_db_and_tables() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.thumbnail_dir.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    run_lightweight_migrations()
    with Session(engine) as session:
        mark_interrupted_scan_jobs(session)
        ensure_initial_admin(session)
        disable_legacy_docker_photos_root_library(session)
        ensure_default_library(session)
        resume_library_cleanups(session)
    from app.api.admin import start_backfill_thread
    start_backfill_thread()


def run_lightweight_migrations() -> None:
    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("user")} if inspector.has_table("user") else set()
    if "is_active" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE user ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
    if "token_version" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE user ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"))
    if "deleted_at" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE user ADD COLUMN deleted_at DATETIME"))
    asset_columns = {column["name"] for column in inspector.get_columns("asset")} if inspector.has_table("asset") else set()
    asset_migrations = {
        "camera_make": "ALTER TABLE asset ADD COLUMN camera_make VARCHAR",
        "camera_model": "ALTER TABLE asset ADD COLUMN camera_model VARCHAR",
        "lens_model": "ALTER TABLE asset ADD COLUMN lens_model VARCHAR",
        "iso": "ALTER TABLE asset ADD COLUMN iso INTEGER",
        "aperture": "ALTER TABLE asset ADD COLUMN aperture VARCHAR",
        "exposure_time": "ALTER TABLE asset ADD COLUMN exposure_time VARCHAR",
        "focal_length": "ALTER TABLE asset ADD COLUMN focal_length VARCHAR",
        "latitude": "ALTER TABLE asset ADD COLUMN latitude REAL",
        "longitude": "ALTER TABLE asset ADD COLUMN longitude REAL",
    }
    with engine.begin() as connection:
        for column, statement in asset_migrations.items():
            if column not in asset_columns:
                connection.execute(text(statement))
    album_columns = {column["name"] for column in inspector.get_columns("photoalbum")} if inspector.has_table("photoalbum") else set()
    if "cover_asset_id" not in album_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE photoalbum ADD COLUMN cover_asset_id INTEGER"))
    share_columns = {column["name"] for column in inspector.get_columns("sharelink")} if inspector.has_table("sharelink") else set()
    if "password_hash" not in share_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE sharelink ADD COLUMN password_hash VARCHAR"))
    scanjob_columns = {column["name"] for column in inspector.get_columns("scanjob")} if inspector.has_table("scanjob") else set()
    scanjob_migrations = {
        "total_estimated": "ALTER TABLE scanjob ADD COLUMN total_estimated INTEGER",
        "processed_assets": "ALTER TABLE scanjob ADD COLUMN processed_assets INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        for column, statement in scanjob_migrations.items():
            if column not in scanjob_columns:
                connection.execute(text(statement))
    asset_indexes = {index["name"] for index in inspector.get_indexes("asset")} if inspector.has_table("asset") else set()
    if "ix_asset_library_path" not in asset_indexes:
        with engine.begin() as connection:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_asset_library_path ON asset(library_id, path)"))
    library_columns = {column["name"] for column in inspector.get_columns("libraryroot")} if inspector.has_table("libraryroot") else set()
    if "deleted_at" not in library_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE libraryroot ADD COLUMN deleted_at DATETIME"))
    if "watch_enabled" not in library_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE libraryroot ADD COLUMN watch_enabled BOOLEAN NOT NULL DEFAULT 0"))
    thumbnail_columns = {column["name"] for column in inspector.get_columns("thumbnail")} if inspector.has_table("thumbnail") else set()
    if "file_size" not in thumbnail_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE thumbnail ADD COLUMN file_size INTEGER"))


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def mark_interrupted_scan_jobs(session: Session) -> None:
    jobs = session.exec(select(ScanJob).where(ScanJob.status.in_({"queued", "running"}))).all()  # type: ignore[attr-defined]
    if not jobs:
        return
    now = utc_now()
    for job in jobs:
        job.status = "failed"
        job.message = "Interrupted by server restart"
        job.finished_at = now
    session.commit()


def ensure_initial_admin(session: Session) -> None:
    existing = session.exec(
        select(User).where(User.email == settings.admin_email.lower(), User.deleted_at == None)
    ).first()
    if existing:
        return
    admin = User(
        email=settings.admin_email.lower(),
        display_name=settings.admin_name,
        role="admin",
        password_hash=hash_password(settings.admin_password),
    )
    session.add(admin)
    session.commit()


def ensure_default_library(session: Session) -> None:
    if not settings.default_library_path:
        return
    if is_docker_photos_root(settings.default_library_path):
        return
    path = Path(settings.default_library_path).resolve()
    if not path.exists() or not path.is_dir():
        return
    existing = session.exec(select(LibraryRoot).where(LibraryRoot.path == str(path))).first()
    if existing:
        return
    session.add(LibraryRoot(name=settings.default_library_name, path=str(path), is_enabled=True))
    session.commit()


def disable_legacy_docker_photos_root_library(session: Session) -> None:
    libraries = session.exec(select(LibraryRoot).where(LibraryRoot.is_enabled == True)).all()  # noqa: E712
    changed = False
    for library in libraries:
        if library.id is None or not is_docker_photos_root(library.path):
            continue
        has_assets = session.exec(select(Asset.id).where(Asset.library_id == library.id).limit(1)).first()
        has_folders = session.exec(select(Folder.id).where(Folder.library_id == library.id).limit(1)).first()
        if has_assets or has_folders:
            continue
        library.is_enabled = False
        session.add(library)
        changed = True
    if changed:
        session.commit()


def resume_library_cleanups(session: Session) -> None:
    stalled = session.exec(select(LibraryRoot).where(LibraryRoot.deleted_at != None)).all()  # noqa: E711
    if not stalled:
        return
    from app.api.admin import _delete_library_cleanup

    for library in stalled:
        library_id = library.id or 0
        _delete_library_cleanup(library_id)
