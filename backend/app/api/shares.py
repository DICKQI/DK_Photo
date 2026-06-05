from __future__ import annotations

from datetime import datetime, timedelta
from secrets import token_urlsafe
from typing import Any

import jwt
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlmodel import select

from app.config import settings
from app.deps import CurrentUser, SessionDep
from app.api.assets import stream_asset_archive
from app.models import Asset, Folder, LibraryRoot, ShareAsset, ShareLink, User
from app.schemas import AssetRead, PublicShareRead, ShareCreate, ShareRead, ShareUpdate, ShareVerifyRequest
from app.security import hash_password, verify_password
from app.services.paths import safe_asset_path
from app.services.permissions import can_access_library, require_asset_access, require_folder_access
from app.services.thumbnails import ensure_thumbnail


router = APIRouter(tags=["shares"])
SHARE_VERIFY_ALGORITHM = "HS256"


def create_share_verify_token(share_token: str) -> str:
    expires_at = datetime.utcnow() + timedelta(hours=1)
    payload: dict[str, Any] = {"sub": share_token, "type": "share_verify", "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=SHARE_VERIFY_ALGORITHM)


def require_share_access(request: Request, share: ShareLink) -> None:
    if not share.password_hash:
        return
    cookie_name = f"dk_photo_share_{share.token}"
    token = request.cookies.get(cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Share password required")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[SHARE_VERIFY_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired share verification")
    if payload.get("sub") != share.token or payload.get("type") != "share_verify":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid share verification")


@router.post("/api/shares", response_model=ShareRead)
def create_share(payload: ShareCreate, session: SessionDep, current_user: CurrentUser) -> ShareRead:
    modes = sum(1 for v in [payload.asset_id, payload.folder_id, payload.asset_ids] if v)
    if modes != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Share exactly one of: asset, folder, or list of assets")
    asset = session.get(Asset, payload.asset_id) if payload.asset_id else None
    folder = session.get(Folder, payload.folder_id) if payload.folder_id else None
    if payload.asset_id and not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    if payload.folder_id and not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    if asset:
        require_asset_access(session, current_user, asset, require_share=True)
    if folder:
        require_folder_access(session, current_user, folder, require_share=True)
    shared_asset_ids: list[int] = []
    if payload.asset_ids:
        if not payload.asset_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset list is empty")
        shared_asset_ids = list(dict.fromkeys(payload.asset_ids))
        db_assets = session.exec(select(Asset).where(Asset.id.in_(shared_asset_ids))).all()
        if len(db_assets) != len(shared_asset_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more assets not found")
        for a in db_assets:
            require_asset_access(session, current_user, a, require_share=True)
    expires_at = None
    if payload.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=payload.expires_in_days)
    if payload.asset_ids:
        title = payload.title or db_assets[0].filename if db_assets else "Shared photos"
    else:
        title = payload.title or (asset.filename if asset else folder.name if folder else "Shared photos")
    password_hash = hash_password(payload.password) if payload.password else None
    share = ShareLink(
        token=token_urlsafe(24),
        creator_id=current_user.id or 0,
        title=title,
        password_hash=password_hash,
        asset_id=payload.asset_id,
        folder_id=payload.folder_id,
        expires_at=expires_at,
    )
    session.add(share)
    session.commit()
    session.refresh(share)
    if payload.asset_ids:
        for aid in shared_asset_ids:
            session.add(ShareAsset(share_id=share.id, asset_id=aid))
        session.commit()
        session.refresh(share)
    return share_read(session, share)


@router.get("/api/shares", response_model=list[ShareRead])
def list_my_shares(session: SessionDep, current_user: CurrentUser) -> list[ShareRead]:
    shares = session.exec(
        select(ShareLink)
        .where(ShareLink.creator_id == current_user.id, ShareLink.revoked_at == None)
        .order_by(ShareLink.created_at.desc())
    ).all()
    return [share_read(session, share) for share in shares]


@router.patch("/api/shares/{share_id}", response_model=ShareRead)
def update_share(share_id: int, payload: ShareUpdate, session: SessionDep, current_user: CurrentUser) -> ShareRead:
    share = session.get(ShareLink, share_id)
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if share.creator_id != (current_user.id or 0):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your share link")
    if share.revoked_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Share is already revoked")
    if payload.title is not None:
        share.title = payload.title
    if payload.expires_in_days is not None:
        if payload.expires_in_days > 0:
            share.expires_at = datetime.utcnow() + timedelta(days=payload.expires_in_days)
        else:
            share.expires_at = None
    if payload.password is not None:
        if payload.password:
            share.password_hash = hash_password(payload.password)
        else:
            share.password_hash = None
    session.add(share)
    session.commit()
    session.refresh(share)
    return share_read(session, share)


@router.delete("/api/shares/{share_id}")
def delete_share(share_id: int, session: SessionDep, current_user: CurrentUser) -> dict:
    share = session.get(ShareLink, share_id)
    if not share:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if share.creator_id != (current_user.id or 0):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your share link")
    if share.revoked_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Share is already revoked")
    share.revoked_at = datetime.utcnow()
    session.add(share)
    session.commit()
    return {"ok": True}


def get_active_share(session: SessionDep, token: str) -> ShareLink:
    share = session.exec(select(ShareLink).where(ShareLink.token == token)).first()
    if not share or share.revoked_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if share.expires_at and share.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Share expired")
    if not creator_can_still_share(session, share):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    return share


def creator_can_still_share(session: SessionDep, share: ShareLink) -> bool:
    creator = session.get(User, share.creator_id)
    if not creator or not creator.is_active or creator.deleted_at:
        return False
    if creator.role == "admin":
        return True
    library_ids = public_share_library_ids(session, share)
    if not library_ids:
        return False
    return all(can_access_library(session, creator, library_id, require_share=True) for library_id in library_ids)


def public_share_library_ids(session: SessionDep, share: ShareLink) -> set[int]:
    if share.asset_id:
        asset = session.get(Asset, share.asset_id)
        return {asset.library_id} if asset else set()
    if share.folder_id:
        folder = session.get(Folder, share.folder_id)
        return {folder.library_id} if folder else set()
    assets = session.exec(
        select(Asset)
        .join(ShareAsset, ShareAsset.asset_id == Asset.id)
        .where(ShareAsset.share_id == share.id)
    ).all()
    return {asset.library_id for asset in assets}


@router.get("/api/public/shares/{token}", response_model=PublicShareRead)
def get_public_share(token: str, session: SessionDep) -> PublicShareRead:
    share = get_active_share(session, token)
    asset_ids = None
    if not share.asset_id and not share.folder_id:
        sa_rows = session.exec(select(ShareAsset).where(ShareAsset.share_id == share.id)).all()
        asset_ids = [sa.asset_id for sa in sa_rows]
    return PublicShareRead(
        token=share.token,
        title=share.title,
        asset_id=share.asset_id,
        folder_id=share.folder_id,
        asset_ids=asset_ids,
        expires_at=share.expires_at,
        has_password=bool(share.password_hash),
    )


@router.post("/api/public/shares/{token}/verify")
def verify_share_password(token: str, payload: ShareVerifyRequest, session: SessionDep, response: Response) -> dict:
    share = get_active_share(session, token)
    if not share.password_hash:
        return {"verified": True, "access_token": None}
    if not verify_password(payload.password, share.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid share password")
    verify_token = create_share_verify_token(share.token)
    response.set_cookie(
        f"dk_photo_share_{share.token}",
        verify_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=3600,
    )
    return {"verified": True, "access_token": verify_token}


@router.get("/api/public/shares/{token}/assets", response_model=list[AssetRead])
def get_public_share_assets(token: str, request: Request, session: SessionDep) -> list[Asset]:
    share = get_active_share(session, token)
    require_share_access(request, share)
    return public_share_assets(session, share)


@router.get("/api/public/shares/{token}/download")
def download_public_share(token: str, request: Request, session: SessionDep):
    share = get_active_share(session, token)
    require_share_access(request, share)
    assets = public_share_assets(session, share)
    if not assets:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No assets in share")
    return stream_asset_archive(session, assets, "dk-photo-share-originals.zip")


def public_share_assets(session: SessionDep, share: ShareLink) -> list[Asset]:
    if share.asset_id:
        asset = session.get(Asset, share.asset_id)
        return [asset] if asset else []
    if share.folder_id:
        return session.exec(select(Asset).where(Asset.folder_id == share.folder_id).order_by(Asset.filename)).all()
    return session.exec(
        select(Asset)
        .join(ShareAsset, ShareAsset.asset_id == Asset.id)
        .where(ShareAsset.share_id == share.id)
        .order_by(Asset.filename)
    ).all()


@router.get("/api/public/shares/{token}/assets/{asset_id}/original")
def get_public_original(token: str, asset_id: int, request: Request, session: SessionDep) -> FileResponse:
    share = get_active_share(session, token)
    require_share_access(request, share)
    asset = session.get(Asset, asset_id)
    if not asset or not _share_contains_asset(session, share, asset):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found in share")
    library = session.get(LibraryRoot, asset.library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    original = safe_asset_path(library.path, asset.path)
    return FileResponse(original, media_type=asset.mime_type, filename=asset.filename)


@router.get("/api/public/shares/{token}/assets/{asset_id}/thumbnail")
def get_public_thumbnail(
    token: str,
    asset_id: int,
    request: Request,
    session: SessionDep,
    size: str = Query(default="medium", pattern="^(small|medium|large)$"),
) -> FileResponse:
    share = get_active_share(session, token)
    require_share_access(request, share)
    asset = session.get(Asset, asset_id)
    if not asset or not _share_contains_asset(session, share, asset):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found in share")
    thumbnail = ensure_thumbnail(session, asset, size)
    return FileResponse(thumbnail, media_type="image/webp", headers={"Cache-Control": "private, max-age=31536000, immutable"})


def _share_contains_asset(session: SessionDep, share: ShareLink, asset: Asset) -> bool:
    if share.asset_id:
        return share.asset_id == asset.id
    if share.folder_id:
        return asset.folder_id == share.folder_id
    return session.exec(
        select(ShareAsset).where(ShareAsset.share_id == share.id, ShareAsset.asset_id == asset.id)
    ).first() is not None


def share_read(session: SessionDep, share: ShareLink) -> ShareRead:
    asset_ids = share_asset_ids(session, share)
    return ShareRead(
        id=share.id or 0,
        token=share.token,
        title=share.title,
        asset_id=share.asset_id,
        folder_id=share.folder_id,
        asset_ids=asset_ids,
        asset_count=share_asset_count(session, share),
        share_kind=share_kind(share),
        expires_at=share.expires_at,
        revoked_at=share.revoked_at,
        created_at=share.created_at,
    )


def share_kind(share: ShareLink) -> str:
    if share.asset_id:
        return "asset"
    if share.folder_id:
        return "folder"
    return "assets"


def share_asset_ids(session: SessionDep, share: ShareLink) -> list[int] | None:
    if share.asset_id or share.folder_id:
        return None
    rows = session.exec(select(ShareAsset.asset_id).where(ShareAsset.share_id == share.id)).all()
    return list(rows)


def share_asset_count(session: SessionDep, share: ShareLink) -> int:
    if share.asset_id:
        return 1
    if share.folder_id:
        return session.exec(select(func.count(Asset.id)).where(Asset.folder_id == share.folder_id)).one()
    return session.exec(select(func.count(ShareAsset.id)).where(ShareAsset.share_id == share.id)).one()
