from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


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
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


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
