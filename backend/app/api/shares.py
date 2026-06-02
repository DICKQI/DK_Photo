from __future__ import annotations

from datetime import datetime, timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlmodel import select

from app.deps import CurrentUser, SessionDep
from app.models import Asset, Folder, LibraryRoot, ShareLink
from app.schemas import AssetRead, PublicShareRead, ShareCreate, ShareRead
from app.services.paths import safe_asset_path
from app.services.permissions import require_asset_access, require_folder_access
from app.services.thumbnails import ensure_thumbnail


router = APIRouter(tags=["shares"])


@router.post("/api/shares", response_model=ShareRead)
def create_share(payload: ShareCreate, session: SessionDep, current_user: CurrentUser) -> ShareLink:
    if bool(payload.asset_id) == bool(payload.folder_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Share exactly one asset or folder")
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
    expires_at = None
    if payload.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=payload.expires_in_days)
    title = payload.title or (asset.filename if asset else folder.name if folder else "Shared photos")
    share = ShareLink(
        token=token_urlsafe(24),
        creator_id=current_user.id or 0,
        title=title,
        asset_id=payload.asset_id,
        folder_id=payload.folder_id,
        expires_at=expires_at,
    )
    session.add(share)
    session.commit()
    session.refresh(share)
    return share


def get_active_share(session: SessionDep, token: str) -> ShareLink:
    share = session.exec(select(ShareLink).where(ShareLink.token == token)).first()
    if not share or share.revoked_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if share.expires_at and share.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Share expired")
    return share


@router.get("/api/public/shares/{token}", response_model=PublicShareRead)
def get_public_share(token: str, session: SessionDep) -> PublicShareRead:
    share = get_active_share(session, token)
    return PublicShareRead(
        token=share.token,
        title=share.title,
        asset_id=share.asset_id,
        folder_id=share.folder_id,
        expires_at=share.expires_at,
    )


@router.get("/api/public/shares/{token}/assets", response_model=list[AssetRead])
def get_public_share_assets(token: str, session: SessionDep) -> list[Asset]:
    share = get_active_share(session, token)
    if share.asset_id:
        asset = session.get(Asset, share.asset_id)
        return [asset] if asset else []
    return session.exec(select(Asset).where(Asset.folder_id == share.folder_id).order_by(Asset.filename)).all()


@router.get("/api/public/shares/{token}/assets/{asset_id}/original")
def get_public_original(token: str, asset_id: int, session: SessionDep) -> FileResponse:
    share = get_active_share(session, token)
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
    session: SessionDep,
    size: str = Query(default="medium", pattern="^(small|medium|large)$"),
) -> FileResponse:
    share = get_active_share(session, token)
    asset = session.get(Asset, asset_id)
    if not asset or not _share_contains_asset(session, share, asset):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found in share")
    thumbnail = ensure_thumbnail(session, asset, size)
    return FileResponse(thumbnail, media_type="image/webp")


def _share_contains_asset(session: SessionDep, share: ShareLink, asset: Asset) -> bool:
    if share.asset_id:
        return share.asset_id == asset.id
    if share.folder_id:
        return asset.folder_id == share.folder_id
    return False
