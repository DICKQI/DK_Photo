from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserRead(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    is_active: bool


class LoginRequest(BaseModel):
    email: str
    password: str


class LibraryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1)
    watch_enabled: bool = False


class LibraryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    watch_enabled: Optional[bool] = None


class LibraryRead(BaseModel):
    id: int
    name: str
    path: str
    is_enabled: bool
    watch_enabled: bool
    created_at: datetime
    last_scan_at: Optional[datetime]
    deleted_at: Optional[datetime] = None


class FolderRead(BaseModel):
    id: int
    library_id: int
    parent_id: Optional[int]
    path: str
    name: str
    photo_count: int
    folder_count: int
    cover_asset_id: Optional[int]
    updated_at: datetime


class FolderDetail(FolderRead):
    ancestors: list[FolderRead] = []


class FolderCoverUpdate(BaseModel):
    cover_asset_id: int


class FolderRenameUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AssetRead(BaseModel):
    id: int
    library_id: int
    folder_id: int
    filename: str
    path: str
    library_name: Optional[str] = None
    folder_name: Optional[str] = None
    folder_path: Optional[str] = None
    mime_type: str
    width: Optional[int]
    height: Optional[int]
    size: int
    mtime: float
    captured_at: Optional[datetime]
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    lens_model: Optional[str] = None
    iso: Optional[int] = None
    aperture: Optional[str] = None
    exposure_time: Optional[str] = None
    focal_length: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    rating: int = Field(default=0, ge=0, le=5)
    updated_at: datetime
    is_favorite: bool = False


class AssetFavoriteUpdate(BaseModel):
    is_favorite: bool


class AssetMetadataUpdate(BaseModel):
    description: str = Field(default="", max_length=2000)
    rating: int = Field(default=0, ge=0, le=5)


class AssetTagsUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=30)


class AssetTagsBulkAdd(BaseModel):
    asset_ids: list[int] = Field(min_length=1, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=30)


class AssetTagsBulkRemove(BaseModel):
    asset_ids: list[int] = Field(min_length=1, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=30)


class AssetTagRename(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class AssetTagRead(BaseModel):
    name: str
    asset_count: int


class AssetRatingRead(BaseModel):
    rating: int = Field(ge=1, le=5)
    asset_count: int


class AssetCameraRead(BaseModel):
    camera_key: str
    label: str
    asset_count: int


class AssetLensRead(BaseModel):
    lens_key: str
    label: str
    asset_count: int


class AssetPlaceRead(BaseModel):
    place_key: str
    label: str
    latitude: float
    longitude: float
    asset_count: int
    cover_asset_id: Optional[int] = None
    latest_at: Optional[datetime] = None


class AssetDownloadRequest(BaseModel):
    asset_ids: list[int] = Field(min_length=1, max_length=500)


class AlbumCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    asset_ids: list[int] = Field(default_factory=list, max_length=500)


class AlbumUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class AlbumAssetAddRequest(BaseModel):
    asset_ids: list[int] = Field(min_length=1, max_length=500)


class AlbumCoverUpdate(BaseModel):
    cover_asset_id: int


class AlbumRead(BaseModel):
    id: int
    name: str
    description: str
    asset_count: int = 0
    cover_asset_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ScanJobRead(BaseModel):
    id: int
    library_id: int
    status: str
    message: str
    total_assets: int
    total_estimated: Optional[int] = None
    processed_assets: int = 0
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class UserCreate(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)
    role: str = "member"


class UserUpdate(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    role: Optional[str] = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=8)


class LibraryPermissionRead(BaseModel):
    user_id: int
    library_id: int
    can_view: bool
    can_share: bool


class LibraryPermissionUpdate(BaseModel):
    library_id: int
    can_view: bool = True
    can_share: bool = False


class FilesystemEntry(BaseModel):
    name: str
    path: str
    is_root: bool = False
    is_accessible: bool = True
    error: Optional[str] = None
    kind: str = "folder"
    group: Optional[str] = None
    child_folder_count: int = 0
    image_count: int = 0
    media_count: int = 0


class FilesystemRoots(BaseModel):
    platform: str
    separator: str
    roots: list[FilesystemEntry]


class FilesystemChildren(BaseModel):
    platform: str
    separator: str
    path: str
    parent_path: Optional[str]
    entries: list[FilesystemEntry]
    child_folder_count: int = 0
    image_count: int = 0
    media_count: int = 0


class ShareCreate(BaseModel):
    title: str = Field(default="", max_length=160)
    asset_id: Optional[int] = None
    folder_id: Optional[int] = None
    asset_ids: Optional[list[int]] = None
    expires_in_days: Optional[int] = Field(default=7, ge=0, le=365)
    password: Optional[str] = Field(default=None, max_length=128)


class ShareRead(BaseModel):
    id: int
    token: str
    title: str
    asset_id: Optional[int]
    folder_id: Optional[int]
    asset_ids: Optional[list[int]] = None
    asset_count: int = 0
    share_kind: str = "assets"
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime


class ShareUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=160)
    expires_in_days: Optional[int] = Field(default=None, ge=0, le=365)
    password: Optional[str] = Field(default=None, max_length=128)


class PublicShareRead(BaseModel):
    token: str
    title: str
    asset_id: Optional[int]
    folder_id: Optional[int]
    asset_ids: Optional[list[int]] = None
    expires_at: Optional[datetime]
    has_password: bool = False


class ShareVerifyRequest(BaseModel):
    password: str


class ThumbnailStats(BaseModel):
    total_count: int = 0
    total_size_bytes: int = 0
    small_count: int = 0
    medium_count: int = 0
    large_count: int = 0


class ServerSettingsRead(BaseModel):
    thumb_workers: int
    cpu_count: int | None
    thumb_workers_default: int


class ServerSettingsUpdate(BaseModel):
    thumb_workers: int = Field(ge=1, le=64)
