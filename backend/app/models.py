from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Index, SQLModel, UniqueConstraint


def utc_now() -> datetime:
    return datetime.utcnow()


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    display_name: str
    role: str = Field(default="member", index=True)
    password_hash: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)


class LibraryPermission(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "library_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    library_id: int = Field(foreign_key="libraryroot.id", index=True)
    can_view: bool = Field(default=True)
    can_share: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)


class LibraryRoot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    path: str = Field(index=True, unique=True)
    is_enabled: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    last_scan_at: Optional[datetime] = None


class Folder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    library_id: int = Field(foreign_key="libraryroot.id", index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="folder.id", index=True)
    path: str = Field(index=True)
    name: str
    photo_count: int = Field(default=0)
    folder_count: int = Field(default=0)
    cover_asset_id: Optional[int] = Field(default=None, foreign_key="asset.id")
    updated_at: datetime = Field(default_factory=utc_now)


class Asset(SQLModel, table=True):
    __table_args__ = (
        Index("ix_asset_library_folder_mime", "library_id", "folder_id", "mime_type"),
        Index("ix_asset_captured_at", "captured_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    library_id: int = Field(foreign_key="libraryroot.id", index=True)
    folder_id: int = Field(foreign_key="folder.id", index=True)
    filename: str = Field(index=True)
    path: str = Field(index=True)
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    size: int = 0
    mtime: float = Field(index=True)
    captured_at: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    lens_model: Optional[str] = None
    iso: Optional[int] = None
    aperture: Optional[str] = None
    exposure_time: Optional[str] = None
    focal_length: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AssetFavorite(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "asset_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)


class AssetTag(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "asset_id", "name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    name: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)


class AssetMetadata(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "asset_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    description: str = ""
    rating: int = Field(default=0, index=True)
    updated_at: datetime = Field(default_factory=utc_now)


class PhotoAlbum(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    name: str
    description: str = ""
    cover_asset_id: Optional[int] = Field(default=None, foreign_key="asset.id")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PhotoAlbumAsset(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("album_id", "asset_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    album_id: int = Field(foreign_key="photoalbum.id", index=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    added_at: datetime = Field(default_factory=utc_now)


class Thumbnail(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    size: str = Field(index=True)
    path: str
    width: int
    height: int
    created_at: datetime = Field(default_factory=utc_now)


class ShareLink(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True)
    creator_id: int = Field(foreign_key="user.id", index=True)
    title: str
    password_hash: Optional[str] = None
    asset_id: Optional[int] = Field(default=None, foreign_key="asset.id", index=True)
    folder_id: Optional[int] = Field(default=None, foreign_key="folder.id", index=True)
    expires_at: Optional[datetime] = Field(default=None, index=True)
    revoked_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class ShareAsset(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("share_id", "asset_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    share_id: int = Field(foreign_key="sharelink.id", index=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)


class ScanJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    library_id: int = Field(foreign_key="libraryroot.id", index=True)
    status: str = Field(default="queued", index=True)
    message: str = ""
    total_assets: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
