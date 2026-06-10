from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import String, cast, func, or_
from sqlmodel import select

from app.deps import CurrentUser, SessionDep
from app.models import Asset, AssetFavorite, AssetMetadata, AssetTag, Folder, LibraryRoot, utc_now
from app.schemas import (
    AssetDownloadRequest,
    AssetCameraRead,
    AssetFavoriteUpdate,
    AssetLensRead,
    AssetMetadataUpdate,
    AssetPlaceRead,
    AssetRatingRead,
    AssetRead,
    AssetTagRead,
    AssetTagRename,
    AssetTagsBulkAdd,
    AssetTagsBulkRemove,
    AssetTagsUpdate,
)
from app.services.operation_log import log_operation
from app.services.paths import safe_asset_path
from app.services.permissions import accessible_library_ids, require_asset_access
from app.services.thumbnails import ensure_thumbnail


router = APIRouter(prefix="/api/assets", tags=["assets"])
PLACE_PRECISION = 2


@router.get("", response_model=list[AssetRead])
def list_assets(
    session: SessionDep,
    current_user: CurrentUser,
    folder_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    recursive: bool = Query(default=False),
    favorites_only: bool = Query(default=False),
    sort: str = Query(default="name", pattern="^(name|recent)$"),
    limit: int | None = Query(default=None, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    media_type: str = Query(default="all", pattern="^(all|image|video)$"),
    has_location: bool = Query(default=False),
    tag: str | None = Query(default=None),
    min_rating: int = Query(default=0, ge=0, le=5),
    camera: str | None = Query(default=None),
    lens: str | None = Query(default=None),
    place: str | None = Query(default=None),
) -> list[AssetRead]:
    statement = select(Asset)
    favorite_ids = current_user_favorite_asset_ids(session, current_user)
    tag_query = normalize_tag_name(tag or "")
    user_id = current_user.id or 0
    if favorites_only:
        if not favorite_ids:
            return []
        statement = statement.where(Asset.id.in_(favorite_ids))
    if tag_query:
        tagged_asset_ids = select(AssetTag.asset_id).where(
            AssetTag.user_id == user_id,
            AssetTag.name == tag_query,
        )
        statement = statement.where(Asset.id.in_(tagged_asset_ids))
    if min_rating > 0:
        rated_asset_ids = select(AssetMetadata.asset_id).where(
            AssetMetadata.user_id == user_id,
            AssetMetadata.rating >= min_rating,
        )
        statement = statement.where(Asset.id.in_(rated_asset_ids))
    camera_filter = (camera or "").strip()
    if camera_filter:
        camera_key = normalize_camera_key(camera_filter)
        if not camera_key:
            return []
        make, model = camera_key_parts(camera_key)
        statement = statement.where(
            func.trim(func.coalesce(Asset.camera_make, "")) == make,
            func.trim(func.coalesce(Asset.camera_model, "")) == model,
        )
    lens_filter = normalize_lens_key(lens or "")
    if lens_filter:
        statement = statement.where(func.trim(func.coalesce(Asset.lens_model, "")) == lens_filter)
    place_filter = normalize_place_key(place or "")
    if place and not place_filter:
        return []
    if place_filter:
        latitude, longitude = place_key_parts(place_filter)
        statement = statement.where(
            func.round(Asset.latitude, PLACE_PRECISION) == latitude,
            func.round(Asset.longitude, PLACE_PRECISION) == longitude,
        )
    if folder_id is not None:
        if recursive:
            folder_ids = {folder_id}
            pending = [folder_id]
            while pending:
                children = session.exec(
                    select(Folder.id).where(Folder.parent_id.in_(pending))
                ).all()
                folder_ids.update(children)
                pending = children
            statement = statement.where(Asset.folder_id.in_(folder_ids))
        else:
            statement = statement.where(Asset.folder_id == folder_id)
    query = search.strip() if search else ""
    if query:
        statement = statement.where(asset_search_filter(query, current_user.id or 0))
    if media_type == "image":
        statement = statement.where(Asset.mime_type.startswith("image/"))
    elif media_type == "video":
        statement = statement.where(Asset.mime_type.startswith("video/"))
    if has_location:
        statement = statement.where(Asset.latitude.is_not(None), Asset.longitude.is_not(None))
    allowed_library_ids = accessible_library_ids(session, current_user)
    if allowed_library_ids is not None:
        if not allowed_library_ids:
            return []
        statement = statement.where(Asset.library_id.in_(allowed_library_ids))
    if sort == "recent":
        statement = statement.order_by(Asset.created_at.desc(), Asset.updated_at.desc(), Asset.filename)
    else:
        statement = statement.order_by(Asset.filename)
    if limit is not None:
        statement = statement.limit(limit)
    if offset:
        statement = statement.offset(offset)
    assets = session.exec(statement).all()
    if not assets:
        return []
    library_ids = {a.library_id for a in assets}
    folder_ids = {a.folder_id for a in assets}
    asset_ids = [a.id for a in assets if a.id is not None]
    libraries = {lib.id: lib for lib in session.exec(select(LibraryRoot).where(LibraryRoot.id.in_(library_ids))).all()} if library_ids else {}
    folders = {f.id: f for f in session.exec(select(Folder).where(Folder.id.in_(folder_ids))).all()} if folder_ids else {}
    metadata_map: dict[int, AssetMetadata] = {}
    if user_id and asset_ids:
        for m in session.exec(select(AssetMetadata).where(AssetMetadata.user_id == user_id, AssetMetadata.asset_id.in_(asset_ids))).all():
            metadata_map[m.asset_id] = m
    tag_map: dict[int, list[str]] = defaultdict(list)
    if user_id and asset_ids:
        for t in session.exec(select(AssetTag).where(AssetTag.user_id == user_id, AssetTag.asset_id.in_(asset_ids)).order_by(AssetTag.name)).all():
            tag_map[t.asset_id].append(t.name)
    return [asset_read(session, asset, favorite_ids, user_id, libraries, folders, metadata_map, tag_map) for asset in assets]


@router.get("/tags", response_model=list[AssetTagRead])
def list_asset_tags(session: SessionDep, current_user: CurrentUser) -> list[AssetTagRead]:
    statement = (
        select(AssetTag.name, func.count(AssetTag.asset_id))
        .join(Asset, Asset.id == AssetTag.asset_id)
        .where(AssetTag.user_id == (current_user.id or 0))
        .group_by(AssetTag.name)
        .order_by(AssetTag.name)
    )
    allowed_library_ids = accessible_library_ids(session, current_user)
    if allowed_library_ids is not None:
        if not allowed_library_ids:
            return []
        statement = statement.where(Asset.library_id.in_(allowed_library_ids))
    return [AssetTagRead(name=name, asset_count=count) for name, count in session.exec(statement).all()]


@router.get("/ratings", response_model=list[AssetRatingRead])
def list_asset_ratings(session: SessionDep, current_user: CurrentUser) -> list[AssetRatingRead]:
    statement = (
        select(AssetMetadata.rating, func.count(AssetMetadata.asset_id))
        .join(Asset, Asset.id == AssetMetadata.asset_id)
        .where(
            AssetMetadata.user_id == (current_user.id or 0),
            AssetMetadata.rating > 0,
        )
        .group_by(AssetMetadata.rating)
    )
    allowed_library_ids = accessible_library_ids(session, current_user)
    if allowed_library_ids is not None:
        if not allowed_library_ids:
            return [AssetRatingRead(rating=rating, asset_count=0) for rating in range(1, 6)]
        statement = statement.where(Asset.library_id.in_(allowed_library_ids))
    exact_counts = {rating: count for rating, count in session.exec(statement).all()}
    return [
        AssetRatingRead(
            rating=rating,
            asset_count=sum(exact_counts.get(exact_rating, 0) for exact_rating in range(rating, 6)),
        )
        for rating in range(1, 6)
    ]


@router.get("/cameras", response_model=list[AssetCameraRead])
def list_asset_cameras(session: SessionDep, current_user: CurrentUser) -> list[AssetCameraRead]:
    statement = (
        select(Asset.camera_make, Asset.camera_model, func.count(Asset.id))
        .where(or_(Asset.camera_make.is_not(None), Asset.camera_model.is_not(None)))
        .group_by(Asset.camera_make, Asset.camera_model)
    )
    allowed_library_ids = accessible_library_ids(session, current_user)
    if allowed_library_ids is not None:
        if not allowed_library_ids:
            return []
        statement = statement.where(Asset.library_id.in_(allowed_library_ids))

    cameras: dict[str, AssetCameraRead] = {}
    for make, model, count in session.exec(statement).all():
        camera_key = camera_key_for_values(make, model)
        if not camera_key:
            continue
        existing = cameras.get(camera_key)
        if existing:
            existing.asset_count += count
        else:
            cameras[camera_key] = AssetCameraRead(
                camera_key=camera_key,
                label=camera_label(make, model),
                asset_count=count,
            )
    return sorted(cameras.values(), key=lambda camera: (-camera.asset_count, camera.label.casefold()))


@router.get("/lenses", response_model=list[AssetLensRead])
def list_asset_lenses(session: SessionDep, current_user: CurrentUser) -> list[AssetLensRead]:
    statement = (
        select(Asset.lens_model, func.count(Asset.id))
        .where(Asset.lens_model.is_not(None))
        .group_by(Asset.lens_model)
    )
    allowed_library_ids = accessible_library_ids(session, current_user)
    if allowed_library_ids is not None:
        if not allowed_library_ids:
            return []
        statement = statement.where(Asset.library_id.in_(allowed_library_ids))

    lenses: dict[str, AssetLensRead] = {}
    for lens_model, count in session.exec(statement).all():
        lens_key = normalize_lens_key(lens_model)
        if not lens_key:
            continue
        existing = lenses.get(lens_key)
        if existing:
            existing.asset_count += count
        else:
            lenses[lens_key] = AssetLensRead(
                lens_key=lens_key,
                label=lens_key,
                asset_count=count,
            )
    return sorted(lenses.values(), key=lambda lens: (-lens.asset_count, lens.label.casefold()))


@router.get("/places", response_model=list[AssetPlaceRead])
def list_asset_places(
    session: SessionDep,
    current_user: CurrentUser,
    search: str | None = Query(default=None),
) -> list[AssetPlaceRead]:
    allowed_ids = accessible_library_ids(session, current_user)
    query = search.strip() if search else ""

    round_lat = func.round(Asset.latitude, PLACE_PRECISION)
    round_lon = func.round(Asset.longitude, PLACE_PRECISION)

    aggregate = (
        select(
            round_lat.label("lat"),
            round_lon.label("lon"),
            func.count(Asset.id).label("cnt"),
            func.max(func.coalesce(Asset.captured_at, Asset.updated_at, Asset.created_at)).label("latest"),
        )
        .where(Asset.latitude.is_not(None), Asset.longitude.is_not(None))
        .group_by(round_lat, round_lon)
    )
    if query:
        aggregate = aggregate.where(asset_search_filter(query, current_user.id or 0))
    if allowed_ids is not None:
        if not allowed_ids:
            return []
        aggregate = aggregate.where(Asset.library_id.in_(allowed_ids))

    rows = session.exec(aggregate).all()
    if not rows:
        return []

    places: list[AssetPlaceRead] = []
    for lat, lon, cnt, latest in rows:
        if lat is None or lon is None:
            continue
        place_key = place_key_for_coordinates(float(lat), float(lon))
        if not place_key:
            continue
        places.append(AssetPlaceRead(
            place_key=place_key,
            label=place_label(float(lat), float(lon)),
            latitude=float(lat),
            longitude=float(lon),
            asset_count=cnt,
            cover_asset_id=None,
            latest_at=latest,
        ))

    places.sort(key=lambda p: (-p.asset_count, -(p.latest_at.timestamp() if p.latest_at else 0), p.label))

    top_places = places[:20]
    for place in top_places:
        cover_stmt = (
            select(Asset.id)
            .where(
                Asset.latitude.is_not(None), Asset.longitude.is_not(None),
                func.round(Asset.latitude, PLACE_PRECISION) == place.latitude,
                func.round(Asset.longitude, PLACE_PRECISION) == place.longitude,
            )
        )
        if query:
            cover_stmt = cover_stmt.where(asset_search_filter(query, current_user.id or 0))
        if allowed_ids is not None:
            cover_stmt = cover_stmt.where(Asset.library_id.in_(allowed_ids))
        cover = session.exec(
            cover_stmt.order_by(func.coalesce(Asset.captured_at, Asset.updated_at, Asset.created_at).desc())
            .limit(1)
        ).first()
        if cover is not None:
            place.cover_asset_id = cover

    return places


@router.post("/bulk-tags", response_model=list[AssetRead])
def add_asset_tags_bulk(
    payload: AssetTagsBulkAdd,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[AssetRead]:
    asset_ids = list(dict.fromkeys(payload.asset_ids))
    tag_names = normalize_tag_names(payload.tags)
    if not tag_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one tag is required")
    assets = session.exec(select(Asset).where(Asset.id.in_(asset_ids))).all()
    assets_by_id = {asset.id: asset for asset in assets}
    if len(assets_by_id) != len(asset_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more assets not found")

    ordered_assets: list[Asset] = []
    user_id = current_user.id or 0
    for asset_id in asset_ids:
        asset = assets_by_id[asset_id]
        require_asset_access(session, current_user, asset)
        ordered_assets.append(asset)

        existing_names = session.exec(
            select(AssetTag.name).where(
                AssetTag.user_id == user_id,
                AssetTag.asset_id == asset_id,
            )
        ).all()
        existing_keys = {name.casefold() for name in existing_names}
        next_count = len(existing_names)
        for name in tag_names:
            if name.casefold() in existing_keys or next_count >= 30:
                continue
            session.add(AssetTag(user_id=user_id, asset_id=asset_id, name=name))
            existing_keys.add(name.casefold())
            next_count += 1

    session.commit()
    log_operation(
        "asset.tags.bulk_add",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="asset",
        message="Bulk tags added",
        metadata={"asset_ids": asset_ids, "tags": tag_names, "asset_count": len(asset_ids)},
    )
    favorite_ids = current_user_favorite_asset_ids(session, current_user)
    return [asset_read(session, asset, favorite_ids, user_id) for asset in ordered_assets]


@router.post("/bulk-tags/remove", response_model=list[AssetRead])
def remove_asset_tags_bulk(
    payload: AssetTagsBulkRemove,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[AssetRead]:
    asset_ids = list(dict.fromkeys(payload.asset_ids))
    tag_names = normalize_tag_names(payload.tags)
    if not tag_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one tag is required")
    assets = session.exec(select(Asset).where(Asset.id.in_(asset_ids))).all()
    assets_by_id = {asset.id: asset for asset in assets}
    if len(assets_by_id) != len(asset_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more assets not found")

    ordered_assets: list[Asset] = []
    user_id = current_user.id or 0
    tag_keys = {name.casefold() for name in tag_names}
    for asset_id in asset_ids:
        asset = assets_by_id[asset_id]
        require_asset_access(session, current_user, asset)
        ordered_assets.append(asset)
        existing = session.exec(
            select(AssetTag).where(
                AssetTag.user_id == user_id,
                AssetTag.asset_id == asset_id,
            )
        ).all()
        for tag in existing:
            if tag.name.casefold() in tag_keys:
                session.delete(tag)

    session.commit()
    log_operation(
        "asset.tags.bulk_remove",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="asset",
        message="Bulk tags removed",
        metadata={"asset_ids": asset_ids, "tags": tag_names, "asset_count": len(asset_ids)},
    )
    favorite_ids = current_user_favorite_asset_ids(session, current_user)
    return [asset_read(session, asset, favorite_ids, user_id) for asset in ordered_assets]


@router.patch("/tags/{tag_name}", response_model=AssetTagRead)
def rename_asset_tag(
    tag_name: str,
    payload: AssetTagRename,
    session: SessionDep,
    current_user: CurrentUser,
) -> AssetTagRead:
    old_name = normalize_tag_name(tag_name)
    new_name = normalize_tag_name(payload.name)
    if not old_name or not new_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag name is required")
    user_id = current_user.id or 0
    tags = accessible_asset_tags(session, current_user, old_name)
    if not tags:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    if old_name != new_name:
        target_tags = accessible_asset_tags(session, current_user, new_name)
        target_asset_ids = {tag.asset_id for tag in target_tags}
        for tag in tags:
            if tag.asset_id in target_asset_ids:
                session.delete(tag)
            else:
                tag.name = new_name
    session.commit()
    count = len(accessible_asset_tags(session, current_user, new_name))
    log_operation(
        "asset.tag.rename",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="tag",
        target_id=new_name,
        message="Asset tag renamed",
        metadata={"old_name": old_name, "new_name": new_name, "asset_count": count},
    )
    return AssetTagRead(name=new_name, asset_count=count)


@router.delete("/tags/{tag_name}", response_model=dict[str, bool])
def delete_asset_tag(tag_name: str, session: SessionDep, current_user: CurrentUser) -> dict[str, bool]:
    name = normalize_tag_name(tag_name)
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag name is required")
    tags = accessible_asset_tags(session, current_user, name)
    if not tags:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    for tag in tags:
        session.delete(tag)
    session.commit()
    log_operation(
        "asset.tag.delete",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="tag",
        target_id=name,
        message="Asset tag deleted",
        metadata={"name": name, "asset_count": len(tags)},
    )
    return {"ok": True}


@router.get("/{asset_id}", response_model=AssetRead)
def get_asset(asset_id: int, session: SessionDep, current_user: CurrentUser) -> AssetRead:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    return asset_read(session, asset, current_user_favorite_asset_ids(session, current_user), current_user.id or 0)


@router.patch("/{asset_id}/favorite", response_model=AssetRead)
def update_asset_favorite(
    asset_id: int,
    payload: AssetFavoriteUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> AssetRead:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    favorite = session.exec(
        select(AssetFavorite).where(
            AssetFavorite.user_id == (current_user.id or 0),
            AssetFavorite.asset_id == asset_id,
        )
    ).first()
    if payload.is_favorite and not favorite:
        session.add(AssetFavorite(user_id=current_user.id or 0, asset_id=asset_id))
        session.commit()
    elif not payload.is_favorite and favorite:
        session.delete(favorite)
        session.commit()
    log_operation(
        "asset.favorite.update",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="asset",
        target_id=asset_id,
        message="Asset favorite updated",
        metadata={"asset_id": asset_id, "is_favorite": payload.is_favorite},
    )
    return asset_read(session, asset, {asset_id} if payload.is_favorite else set(), current_user.id or 0)


@router.patch("/{asset_id}/metadata", response_model=AssetRead)
def update_asset_metadata(
    asset_id: int,
    payload: AssetMetadataUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> AssetRead:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    user_id = current_user.id or 0
    metadata = asset_metadata(session, asset_id, user_id)
    description = payload.description.strip()
    rating = payload.rating
    if not description and rating == 0:
        if metadata:
            session.delete(metadata)
            session.commit()
    else:
        if metadata:
            metadata.description = description
            metadata.rating = rating
            metadata.updated_at = utc_now()
        else:
            metadata = AssetMetadata(
                user_id=user_id,
                asset_id=asset_id,
                description=description,
                rating=rating,
                updated_at=utc_now(),
            )
            session.add(metadata)
        session.commit()
    log_operation(
        "asset.metadata.update",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="asset",
        target_id=asset_id,
        message="Asset metadata updated",
        metadata={"asset_id": asset_id, "has_description": bool(description), "rating": rating},
    )
    return asset_read(session, asset, current_user_favorite_asset_ids(session, current_user), user_id)


@router.patch("/{asset_id}/tags", response_model=AssetRead)
def update_asset_tags(
    asset_id: int,
    payload: AssetTagsUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> AssetRead:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    tag_names = normalize_tag_names(payload.tags)
    existing = session.exec(
        select(AssetTag).where(
            AssetTag.user_id == (current_user.id or 0),
            AssetTag.asset_id == asset_id,
        )
    ).all()
    for tag in existing:
        session.delete(tag)
    session.flush()
    for name in tag_names:
        session.add(AssetTag(user_id=current_user.id or 0, asset_id=asset_id, name=name))
    session.commit()
    log_operation(
        "asset.tags.update",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="asset",
        target_id=asset_id,
        message="Asset tags updated",
        metadata={"asset_id": asset_id, "tags": tag_names, "tag_count": len(tag_names)},
    )
    return asset_read(session, asset, current_user_favorite_asset_ids(session, current_user), current_user.id or 0)


@router.post("/download")
def download_assets(payload: AssetDownloadRequest, session: SessionDep, current_user: CurrentUser) -> StreamingResponse:
    asset_ids = list(dict.fromkeys(payload.asset_ids))
    assets = session.exec(select(Asset).where(Asset.id.in_(asset_ids))).all()
    assets_by_id = {asset.id: asset for asset in assets}
    if len(assets_by_id) != len(asset_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more assets not found")

    ordered_assets: list[Asset] = []
    for asset_id in asset_ids:
        asset = assets_by_id[asset_id]
        require_asset_access(session, current_user, asset)
        ordered_assets.append(asset)
    log_operation(
        "asset.download",
        category="audit",
        status="success",
        actor_id=current_user.id,
        target_type="asset",
        message="Assets downloaded",
        metadata={"asset_ids": asset_ids, "asset_count": len(asset_ids)},
    )
    return stream_asset_archive(session, ordered_assets, "dk-photo-originals.zip")


def stream_asset_archive(session: SessionDep, assets: list[Asset], filename: str) -> StreamingResponse:
    archive = BytesIO()
    used_names: set[str] = set()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
        for asset in assets:
            library = session.get(LibraryRoot, asset.library_id)
            if not library:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
            original = safe_asset_path(library.path, asset.path)
            zip_file.write(original, unique_archive_name(asset, used_names))
    archive.seek(0)
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{asset_id}/original")
def get_original(asset_id: int, session: SessionDep, current_user: CurrentUser) -> FileResponse:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    library = session.get(LibraryRoot, asset.library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    original = safe_asset_path(library.path, asset.path)
    return FileResponse(original, media_type=asset.mime_type, filename=asset.filename)


@router.get("/{asset_id}/thumbnail")
def get_thumbnail(
    asset_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    size: str = Query(default="medium", pattern="^(small|medium|large)$"),
) -> FileResponse:
    asset = session.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    require_asset_access(session, current_user, asset)
    thumbnail = ensure_thumbnail(session, asset, size)
    return FileResponse(thumbnail, media_type="image/webp", headers={"Cache-Control": "private, max-age=31536000, immutable"})


def current_user_favorite_asset_ids(session: SessionDep, current_user: CurrentUser) -> set[int]:
    rows = session.exec(
        select(AssetFavorite.asset_id).where(AssetFavorite.user_id == (current_user.id or 0))
    ).all()
    return set(rows)


def normalize_camera_part(value: str | None) -> str:
    return " ".join((value or "").split())


def camera_key_for_values(make: str | None, model: str | None) -> str:
    normalized_make = normalize_camera_part(make)
    normalized_model = normalize_camera_part(model)
    if not normalized_make and not normalized_model:
        return ""
    return f"{normalized_make}|{normalized_model}"


def normalize_camera_key(value: str) -> str:
    key = value.strip()
    if "|" not in key:
        return ""
    make, model = key.split("|", 1)
    return camera_key_for_values(make, model)


def camera_key_parts(camera_key: str) -> tuple[str, str]:
    make, model = camera_key.split("|", 1)
    return make, model


def camera_label(make: str | None, model: str | None) -> str:
    parts = [normalize_camera_part(make), normalize_camera_part(model)]
    return " ".join(part for part in parts if part)


def normalize_lens_key(value: str | None) -> str:
    return normalize_camera_part(value)


def place_key_for_coordinates(latitude: float | None, longitude: float | None) -> str:
    if latitude is None or longitude is None:
        return ""
    return f"{round_place_coordinate(latitude):.{PLACE_PRECISION}f},{round_place_coordinate(longitude):.{PLACE_PRECISION}f}"


def normalize_place_key(value: str) -> str:
    key = value.strip()
    if "," not in key:
        return ""
    latitude_raw, longitude_raw = key.split(",", 1)
    try:
        latitude = float(latitude_raw.strip())
        longitude = float(longitude_raw.strip())
    except ValueError:
        return ""
    return place_key_for_coordinates(latitude, longitude)


def place_key_parts(place_key: str) -> tuple[float, float]:
    latitude, longitude = place_key.split(",", 1)
    return float(latitude), float(longitude)


def round_place_coordinate(value: float) -> float:
    rounded = round(value, PLACE_PRECISION)
    return 0 if rounded == 0 else rounded


def place_label(latitude: float, longitude: float) -> str:
    return f"{latitude:.{PLACE_PRECISION}f}, {longitude:.{PLACE_PRECISION}f}"


def asset_place_datetime(asset: Asset):
    return asset.captured_at or asset.updated_at or asset.created_at


def asset_search_filter(search: str, user_id: int | None = None):
    folder_matches = select(Folder.id).where(or_(Folder.name.contains(search), Folder.path.contains(search)))
    library_matches = select(LibraryRoot.id).where(LibraryRoot.name.contains(search))
    tag_matches = select(AssetTag.asset_id).where(AssetTag.name.contains(search))
    metadata_matches = select(AssetMetadata.asset_id).where(AssetMetadata.description.contains(search))
    if user_id is not None:
        tag_matches = tag_matches.where(AssetTag.user_id == user_id)
        metadata_matches = metadata_matches.where(AssetMetadata.user_id == user_id)
    return or_(
        Asset.filename.contains(search),
        Asset.path.contains(search),
        Asset.mime_type.contains(search),
        Asset.camera_make.contains(search),
        Asset.camera_model.contains(search),
        Asset.lens_model.contains(search),
        Asset.aperture.contains(search),
        Asset.exposure_time.contains(search),
        Asset.focal_length.contains(search),
        cast(Asset.iso, String).contains(search),
        cast(Asset.captured_at, String).contains(search),
        Asset.folder_id.in_(folder_matches),
        Asset.library_id.in_(library_matches),
        Asset.id.in_(tag_matches),
        Asset.id.in_(metadata_matches),
    )


def unique_archive_name(asset: Asset, used_names: set[str]) -> str:
    base_name = safe_archive_name(asset)
    candidate = base_name
    index = 2
    while candidate in used_names:
        path = PurePosixPath(base_name)
        parent = "" if str(path.parent) == "." else f"{path.parent}/"
        candidate = f"{parent}{path.stem or 'photo'} ({index}){path.suffix}"
        index += 1
    used_names.add(candidate)
    return candidate


def safe_archive_name(asset: Asset) -> str:
    raw_name = (asset.path or asset.filename or f"asset-{asset.id}").replace("\\", "/")
    parts = [part.strip() for part in raw_name.split("/") if part.strip() and part not in {".", ".."}]
    return "/".join(parts) or asset.filename or f"asset-{asset.id}"


def asset_read(session: SessionDep, asset: Asset, favorite_ids: set[int], tag_user_id: int | None = None,
               libraries: dict[int, LibraryRoot] | None = None, folders: dict[int, Folder] | None = None,
               metadata_map: dict[int, AssetMetadata] | None = None, tag_map: dict[int, list[str]] | None = None) -> AssetRead:
    library = libraries.get(asset.library_id) if libraries else session.get(LibraryRoot, asset.library_id)
    folder = folders.get(asset.folder_id) if folders else session.get(Folder, asset.folder_id)
    metadata = metadata_map.get(asset.id or 0) if metadata_map else (asset_metadata(session, asset.id or 0, tag_user_id) if tag_user_id else None)
    tags = tag_map.get(asset.id or 0, []) if tag_map else (asset_tag_names(session, asset.id or 0, tag_user_id) if tag_user_id else [])
    return AssetRead(
        id=asset.id or 0,
        library_id=asset.library_id,
        folder_id=asset.folder_id,
        filename=asset.filename,
        path=asset.path,
        library_name=library.name if library else None,
        folder_name=folder.name if folder else None,
        folder_path=folder.path if folder else None,
        mime_type=asset.mime_type,
        width=asset.width,
        height=asset.height,
        size=asset.size,
        mtime=asset.mtime,
        captured_at=asset.captured_at,
        camera_make=asset.camera_make,
        camera_model=asset.camera_model,
        lens_model=asset.lens_model,
        iso=asset.iso,
        aperture=asset.aperture,
        exposure_time=asset.exposure_time,
        focal_length=asset.focal_length,
        latitude=asset.latitude,
        longitude=asset.longitude,
        tags=tags,
        description=metadata.description if metadata else "",
        rating=metadata.rating if metadata else 0,
        updated_at=asset.updated_at,
        is_favorite=(asset.id or 0) in favorite_ids,
    )


def asset_metadata(session: SessionDep, asset_id: int, user_id: int | None) -> AssetMetadata | None:
    if not user_id:
        return None
    return session.exec(
        select(AssetMetadata).where(
            AssetMetadata.user_id == user_id,
            AssetMetadata.asset_id == asset_id,
        )
    ).first()


def asset_tag_names(session: SessionDep, asset_id: int, user_id: int | None) -> list[str]:
    if not user_id:
        return []
    rows = session.exec(
        select(AssetTag.name)
        .where(AssetTag.user_id == user_id, AssetTag.asset_id == asset_id)
        .order_by(AssetTag.name)
    ).all()
    return list(rows)


def accessible_asset_tags(session: SessionDep, current_user: CurrentUser, name: str) -> list[AssetTag]:
    statement = (
        select(AssetTag)
        .join(Asset, Asset.id == AssetTag.asset_id)
        .where(
            AssetTag.user_id == (current_user.id or 0),
            AssetTag.name == name,
        )
    )
    allowed_library_ids = accessible_library_ids(session, current_user)
    if allowed_library_ids is not None:
        if not allowed_library_ids:
            return []
        statement = statement.where(Asset.library_id.in_(allowed_library_ids))
    return list(session.exec(statement).all())


def normalize_tag_names(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        name = normalize_tag_name(value)
        key = name.casefold()
        if not name or key in seen:
            continue
        normalized.append(name)
        seen.add(key)
        if len(normalized) >= 30:
            break
    return normalized


def normalize_tag_name(value: str) -> str:
    return " ".join(value.strip().split())[:40]
