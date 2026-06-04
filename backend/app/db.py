from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import settings
from app.models import LibraryRoot, User
from app.security import hash_password


connect_args = {"check_same_thread": False}
engine = create_engine(settings.database_url, connect_args=connect_args)


def create_db_and_tables() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.thumbnail_dir.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    run_lightweight_migrations()
    with Session(engine) as session:
        ensure_initial_admin(session)
        ensure_default_library(session)


def run_lightweight_migrations() -> None:
    inspector = inspect(engine)
    user_columns = {column["name"] for column in inspector.get_columns("user")} if inspector.has_table("user") else set()
    if "is_active" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE user ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
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


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def ensure_initial_admin(session: Session) -> None:
    existing = session.exec(select(User).where(User.email == settings.admin_email.lower())).first()
    if existing:
        return
    admin = User(
        email=settings.admin_email.lower(),
        display_name="Administrator",
        role="admin",
        password_hash=hash_password(settings.admin_password),
    )
    session.add(admin)
    session.commit()


def ensure_default_library(session: Session) -> None:
    if not settings.default_library_path:
        return
    path = Path(settings.default_library_path).resolve()
    if not path.exists() or not path.is_dir():
        return
    existing = session.exec(select(LibraryRoot).where(LibraryRoot.path == str(path))).first()
    if existing:
        return
    session.add(LibraryRoot(name=settings.default_library_name, path=str(path), is_enabled=True))
    session.commit()
