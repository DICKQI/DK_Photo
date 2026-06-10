from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import select

from app.api.assets import asset_read, asset_search_filter, current_user_favorite_asset_ids
from app.deps import CurrentUser, SessionDep
from app.models import Asset, AssetMetadata, PhotoAlbum, PhotoAlbumAsset, utc_now
from app.schemas import AlbumAssetAddRequest, AlbumCoverUpdate, AlbumCreate, AlbumRead, AlbumUpdate, AssetRead
from app.services.operation_log import log_operation
from app.services.permissions import accessible_library_ids, require_asset_access


router = APIRouter(prefix="/api/albums", tags=["albums"])


@router.get("", response_model=list[AlbumRead])
def list_albums(session: SessionDep, current_user: CurrentUser) -> list[AlbumRead]:
    albums = session.exec(
        select(PhotoAlbum)
        .where(PhotoAlbum.owner_id == (current_user.id or 0))
        .order_by(PhotoAlbum.updated_at.desc(), PhotoAlbum.name)
    ).all()
    return [album_read(session, album) for album in albums]


@router.post("", response_model=AlbumRead)
def create_album(payload: AlbumCreate, session: SessionDep, current_user: CurrentUser) -> AlbumRead:
    album = PhotoAlbum(
        owner_id=current_user.id or 0,
        name=payload.name.strip(),
        description=payload.description.strip(),
    )
    if not album.name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Album name is required")

    session.add(album)
    session.commit()
    session.refresh(album)
    if payload.asset_ids:
        add_assets_to_album(session, current_user, album, payload.asset_ids)
    log_operation(
        "album.create",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="album",
        target_id=album.id,
        message="Album created",
        metadata={"name": album.name, "asset_count": len(set(payload.asset_ids or []))},
    )
    return album_read(session, album)


@router.get("/{album_id}", response_model=AlbumRead)
def get_album(album_id: int, session: SessionDep, current_user: CurrentUser) -> AlbumRead:
    return album_read(session, require_owned_album(session, current_user, album_id))


@router.patch("/{album_id}", response_model=AlbumRead)
def update_album(
    album_id: int,
    payload: AlbumUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> AlbumRead:
    album = require_owned_album(session, current_user, album_id)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Album name is required")
        album.name = name
    if payload.description is not None:
        album.description = payload.description.strip()
    album.updated_at = utc_now()
    session.add(album)
    session.commit()
    session.refresh(album)
    log_operation(
        "album.update",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="album",
        target_id=album.id,
        message="Album updated",
        metadata={"name_changed": payload.name is not None, "description_changed": payload.description is not None},
    )
    return album_read(session, album)


@router.patch("/{album_id}/cover", response_model=AlbumRead)
def update_album_cover(
    album_id: int,
    payload: AlbumCoverUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> AlbumRead:
    album = require_owned_album(session, current_user, album_id)
    membership = session.exec(
        select(PhotoAlbumAsset).where(
            PhotoAlbumAsset.album_id == album.id,
            PhotoAlbumAsset.asset_id == payload.cover_asset_id,
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cover photo must belong to this album")
    asset = session.get(Asset, payload.cover_asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    album.cover_asset_id = payload.cover_asset_id
    album.updated_at = utc_now()
    session.add(album)
    session.commit()
    session.refresh(album)
    log_operation(
        "album.cover.update",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="album",
        target_id=album.id,
        message="Album cover updated",
        metadata={"cover_asset_id": payload.cover_asset_id},
    )
    return album_read(session, album)


@router.get("/{album_id}/assets", response_model=list[AssetRead])
def list_album_assets(
    album_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    search: str | None = Query(default=None),
    media_type: str = Query(default="all", pattern="^(all|image|video)$"),
    min_rating: int = Query(default=0, ge=0, le=5),
) -> list[AssetRead]:
    album = require_owned_album(session, current_user, album_id)
    statement = (
        select(Asset)
        .join(PhotoAlbumAsset, PhotoAlbumAsset.asset_id == Asset.id)
        .where(PhotoAlbumAsset.album_id == album.id)
    )
    query = search.strip() if search else ""
    if query:
        statement = statement.where(asset_search_filter(query, current_user.id or 0))
    if min_rating > 0:
        rated_asset_ids = select(AssetMetadata.asset_id).where(
            AssetMetadata.user_id == (current_user.id or 0),
            AssetMetadata.rating >= min_rating,
        )
        statement = statement.where(Asset.id.in_(rated_asset_ids))
    if media_type == "image":
        statement = statement.where(Asset.mime_type.startswith("image/"))
    elif media_type == "video":
        statement = statement.where(Asset.mime_type.startswith("video/"))
    allowed_library_ids = accessible_library_ids(session, current_user)
    if allowed_library_ids is not None:
        if not allowed_library_ids:
            return []
        statement = statement.where(Asset.library_id.in_(allowed_library_ids))
    statement = statement.order_by(PhotoAlbumAsset.added_at, Asset.filename)
    favorite_ids = current_user_favorite_asset_ids(session, current_user)
    return [asset_read(session, asset, favorite_ids, current_user.id or 0) for asset in session.exec(statement).all()]


@router.post("/{album_id}/assets", response_model=AlbumRead)
def add_album_assets(
    album_id: int,
    payload: AlbumAssetAddRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> AlbumRead:
    album = require_owned_album(session, current_user, album_id)
    add_assets_to_album(session, current_user, album, payload.asset_ids)
    log_operation(
        "album.assets.add",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="album",
        target_id=album.id,
        message="Assets added to album",
        metadata={"asset_ids": list(dict.fromkeys(payload.asset_ids)), "requested_count": len(payload.asset_ids)},
    )
    return album_read(session, album)


@router.delete("/{album_id}/assets", response_model=AlbumRead)
def remove_album_assets(
    album_id: int,
    payload: AlbumAssetAddRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> AlbumRead:
    album = require_owned_album(session, current_user, album_id)
    remove_assets_from_album(session, album, payload.asset_ids)
    log_operation(
        "album.assets.remove",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="album",
        target_id=album.id,
        message="Assets removed from album",
        metadata={"asset_ids": list(dict.fromkeys(payload.asset_ids)), "requested_count": len(payload.asset_ids)},
    )
    return album_read(session, album)


@router.delete("/{album_id}")
def delete_album(album_id: int, session: SessionDep, current_user: CurrentUser) -> dict:
    album = require_owned_album(session, current_user, album_id)
    rows = session.exec(select(PhotoAlbumAsset).where(PhotoAlbumAsset.album_id == album.id)).all()
    for row in rows:
        session.delete(row)
    session.delete(album)
    session.commit()
    log_operation(
        "album.delete",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="album",
        target_id=album_id,
        message="Album deleted",
        metadata={"asset_count": len(rows)},
    )
    return {"ok": True}


def require_owned_album(session: SessionDep, current_user: CurrentUser, album_id: int) -> PhotoAlbum:
    album = session.get(PhotoAlbum, album_id)
    if not album or album.owner_id != (current_user.id or 0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
    return album


def add_assets_to_album(
    session: SessionDep,
    current_user: CurrentUser,
    album: PhotoAlbum,
    requested_asset_ids: list[int],
) -> None:
    asset_ids = list(dict.fromkeys(requested_asset_ids))
    assets = session.exec(select(Asset).where(Asset.id.in_(asset_ids))).all()
    if len(assets) != len(asset_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more assets not found")
    assets_by_id = {asset.id: asset for asset in assets}
    for asset_id in asset_ids:
        require_asset_access(session, current_user, assets_by_id[asset_id])

    existing_ids = set(
        session.exec(select(PhotoAlbumAsset.asset_id).where(PhotoAlbumAsset.album_id == album.id)).all()
    )
    added = False
    for asset_id in asset_ids:
        if asset_id in existing_ids:
            continue
        session.add(PhotoAlbumAsset(album_id=album.id or 0, asset_id=asset_id))
        added = True
    if added:
        album.updated_at = utc_now()
        session.add(album)
        session.commit()
        session.refresh(album)


def remove_assets_from_album(session: SessionDep, album: PhotoAlbum, requested_asset_ids: list[int]) -> None:
    asset_ids = list(dict.fromkeys(requested_asset_ids))
    rows = session.exec(
        select(PhotoAlbumAsset).where(
            PhotoAlbumAsset.album_id == album.id,
            PhotoAlbumAsset.asset_id.in_(asset_ids),  # type: ignore[attr-defined]
        )
    ).all()
    if not rows:
        return
    for row in rows:
        session.delete(row)
    if album.cover_asset_id in asset_ids:
        album.cover_asset_id = None
    album.updated_at = utc_now()
    session.add(album)
    session.commit()
    session.refresh(album)


def album_read(session: SessionDep, album: PhotoAlbum) -> AlbumRead:
    asset_count = session.exec(
        select(func.count(PhotoAlbumAsset.id)).where(PhotoAlbumAsset.album_id == album.id)
    ).one()
    cover_asset_id = album.cover_asset_id or session.exec(
        select(PhotoAlbumAsset.asset_id)
        .where(PhotoAlbumAsset.album_id == album.id)
        .order_by(PhotoAlbumAsset.added_at, PhotoAlbumAsset.id)
    ).first()
    return AlbumRead(
        id=album.id or 0,
        name=album.name,
        description=album.description,
        asset_count=asset_count,
        cover_asset_id=cover_asset_id,
        created_at=album.created_at,
        updated_at=album.updated_at,
    )
