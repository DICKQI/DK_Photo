from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import Asset, Folder, LibraryPermission, User


def accessible_library_ids(session: Session, user: User, require_share: bool = False) -> list[int] | None:
    if user.role == "admin":
        return None
    statement = select(LibraryPermission).where(
        LibraryPermission.user_id == user.id,
        LibraryPermission.can_view == True,  # noqa: E712
    )
    if require_share:
        statement = statement.where(LibraryPermission.can_share == True)  # noqa: E712
    permissions = session.exec(statement).all()
    return [permission.library_id for permission in permissions]


def can_access_library(session: Session, user: User, library_id: int, require_share: bool = False) -> bool:
    if user.role == "admin":
        return True
    statement = select(LibraryPermission).where(
        LibraryPermission.user_id == user.id,
        LibraryPermission.library_id == library_id,
        LibraryPermission.can_view == True,  # noqa: E712
    )
    if require_share:
        statement = statement.where(LibraryPermission.can_share == True)  # noqa: E712
    return session.exec(statement).first() is not None


def require_library_access(session: Session, user: User, library_id: int, require_share: bool = False) -> None:
    if not can_access_library(session, user, library_id, require_share=require_share):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this library")


def require_folder_access(session: Session, user: User, folder: Folder, require_share: bool = False) -> None:
    require_library_access(session, user, folder.library_id, require_share=require_share)


def require_asset_access(session: Session, user: User, asset: Asset, require_share: bool = False) -> None:
    require_library_access(session, user, asset.library_id, require_share=require_share)
