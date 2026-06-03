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


class LibraryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)


class LibraryRead(BaseModel):
    id: int
    name: str
    path: str
    is_enabled: bool
    created_at: datetime
    last_scan_at: Optional[datetime]


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


class AssetRead(BaseModel):
    id: int
    library_id: int
    folder_id: int
    filename: str
    path: str
    mime_type: str
    width: Optional[int]
    height: Optional[int]
    size: int
    mtime: float
    captured_at: Optional[datetime]
    updated_at: datetime


class ScanJobRead(BaseModel):
    id: int
    library_id: int
    status: str
    message: str
    total_assets: int
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


class ShareCreate(BaseModel):
    title: str = Field(default="", max_length=160)
    asset_id: Optional[int] = None
    folder_id: Optional[int] = None
    asset_ids: Optional[list[int]] = None
    expires_in_days: Optional[int] = Field(default=7, ge=1, le=365)


class ShareRead(BaseModel):
    id: int
    token: str
    title: str
    asset_id: Optional[int]
    folder_id: Optional[int]
    asset_ids: Optional[list[int]] = None
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime


class PublicShareRead(BaseModel):
    token: str
    title: str
    asset_id: Optional[int]
    folder_id: Optional[int]
    asset_ids: Optional[list[int]] = None
    expires_at: Optional[datetime]
