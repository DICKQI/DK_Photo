from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, SQLModel, create_engine, select

from app.config import settings
from app.db import ensure_initial_admin, get_session
from app.main import app
from app.models import Asset, AssetMetadata, AssetTag, Folder, LibraryPermission, LibraryRoot, ScanJob, ShareLink, Thumbnail, User
from app.security import hash_password, verify_password
from app.services.scanner import scan_library


def create_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "#3b82f6").save(path)


def login(client: TestClient, email: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


def filenames(response) -> set[str]:
    assert response.status_code == 200, response.text
    return {asset["filename"] for asset in response.json()}


def isolated_client(tmp_path: Path) -> tuple[TestClient, object]:
    engine = create_engine(f"sqlite:///{tmp_path / 'api-test.sqlite3'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        from app.models import User

        session.add(
            User(
                email="admin@example.com",
                display_name="Administrator",
                role="admin",
                password_hash=hash_password("change-me-now"),
            )
        )
        session.commit()

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app), engine


def test_initial_admin_uses_configured_display_name(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'admin-name.sqlite3'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    old_name = settings.admin_name
    old_email = settings.admin_email
    old_password = settings.admin_password

    try:
        object.__setattr__(settings, "admin_name", "Deploy Owner")
        object.__setattr__(settings, "admin_email", f"owner-{tmp_path.name}@example.com")
        object.__setattr__(settings, "admin_password", "owner-pass-123")

        with Session(engine) as session:
            ensure_initial_admin(session)
            admin = session.exec(select(User).where(User.email == settings.admin_email.lower())).first()

        assert admin is not None
        assert admin.display_name == "Deploy Owner"
        assert admin.role == "admin"
        assert verify_password("owner-pass-123", admin.password_hash)
    finally:
        object.__setattr__(settings, "admin_name", old_name)
        object.__setattr__(settings, "admin_email", old_email)
        object.__setattr__(settings, "admin_password", old_password)


def test_admin_filesystem_requires_auth(tmp_path: Path) -> None:
    client, _ = isolated_client(tmp_path)
    with client:
        response = client.get("/api/admin/filesystem/roots")
        assert response.status_code == 401
    app.dependency_overrides.clear()


def test_admin_settings_include_thumbnail_memory_guard_status(tmp_path: Path, monkeypatch) -> None:
    from app.services import resource_limits

    monkeypatch.setattr(
        resource_limits,
        "current_memory_status",
        lambda: resource_limits.MemoryStatus(
            guard_enabled=True,
            total_bytes=6 * 1024 * 1024 * 1024,
            available_bytes=4 * 1024 * 1024 * 1024,
            thumbnail_budget_bytes=2 * 1024 * 1024 * 1024,
        ),
    )

    client, _ = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        response = client.get("/api/admin/settings")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["memory_guard_enabled"] is True
    assert data["memory_total_bytes"] == 6 * 1024 * 1024 * 1024
    assert data["memory_available_bytes"] == 4 * 1024 * 1024 * 1024
    assert data["thumbnail_memory_budget_bytes"] == 2 * 1024 * 1024 * 1024
    app.dependency_overrides.clear()


def test_admin_can_manage_users_and_permissions(tmp_path: Path) -> None:
    email = f"member-{tmp_path.name}@example.com"
    client, _ = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        create_user = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Member",
                "password": "password123",
                "role": "member",
            },
        )
        assert create_user.status_code == 200, create_user.text
        user_id = create_user.json()["id"]

        update_user = client.patch(
            f"/api/admin/users/{user_id}",
            json={"display_name": "Family Member", "role": "member"},
        )
        assert update_user.status_code == 200
        assert update_user.json()["display_name"] == "Family Member"

        reset_password = client.post(f"/api/admin/users/{user_id}/password", json={"password": "newpass123"})
        assert reset_password.status_code == 200

        disable = client.post(f"/api/admin/users/{user_id}/disable")
        assert disable.status_code == 200
        assert disable.json()["is_active"] is False

        enable = client.post(f"/api/admin/users/{user_id}/enable")
        assert enable.status_code == 200
        assert enable.json()["is_active"] is True

        photo_root = tmp_path / "photos"
        create_photo(photo_root / "one.jpg")
        library_response = client.post("/api/admin/libraries", json={"name": f"Managed {tmp_path.name}", "path": str(photo_root)})
        assert library_response.status_code == 200, library_response.text
        library_id = library_response.json()["id"]

        permissions = client.put(
            f"/api/admin/users/{user_id}/permissions",
            json=[{"library_id": library_id, "can_view": True, "can_share": True}],
        )
        assert permissions.status_code == 200
        assert permissions.json()[0]["can_share"] is True
    app.dependency_overrides.clear()


def test_admin_can_update_library_name(tmp_path: Path) -> None:
    client, _ = isolated_client(tmp_path)
    photo_root = tmp_path / "rename-photos"
    create_photo(photo_root / "one.jpg")

    with client:
        login(client, "admin@example.com", "change-me-now")
        library_response = client.post("/api/admin/libraries", json={"name": "Original name", "path": str(photo_root)})
        assert library_response.status_code == 200, library_response.text
        library_id = library_response.json()["id"]

        update_response = client.patch(f"/api/admin/libraries/{library_id}", json={"name": "  Holiday Archive  "})
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["name"] == "Holiday Archive"

        missing_response = client.patch("/api/admin/libraries/999999", json={"name": "Missing"})
        assert missing_response.status_code == 404
    app.dependency_overrides.clear()


def test_member_cannot_update_or_delete_libraries(tmp_path: Path) -> None:
    client, _ = isolated_client(tmp_path)
    photo_root = tmp_path / "member-protected"
    create_photo(photo_root / "one.jpg")

    with client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": f"member-admin-{tmp_path.name}@example.com",
                "display_name": "Member",
                "password": "password123",
                "role": "member",
            },
        )
        assert member.status_code == 200, member.text
        library_response = client.post("/api/admin/libraries", json={"name": "Protected", "path": str(photo_root)})
        assert library_response.status_code == 200, library_response.text
        library_id = library_response.json()["id"]

        login(client, f"member-admin-{tmp_path.name}@example.com", "password123")
        update_response = client.patch(f"/api/admin/libraries/{library_id}", json={"name": "Nope"})
        delete_response = client.delete(f"/api/admin/libraries/{library_id}")

        assert update_response.status_code == 403
        assert delete_response.status_code == 403
    app.dependency_overrides.clear()


def test_deleted_user_token_cannot_authenticate_recreated_user(tmp_path: Path) -> None:
    client, _ = isolated_client(tmp_path)
    old_member_client = TestClient(app)
    old_email = f"old-token-{tmp_path.name}@example.com"
    new_email = f"new-token-{tmp_path.name}@example.com"

    with client, old_member_client:
        login(client, "admin@example.com", "change-me-now")
        created = client.post(
            "/api/admin/users",
            json={
                "email": old_email,
                "display_name": "Old Member",
                "password": "password123",
                "role": "member",
            },
        )
        assert created.status_code == 200, created.text
        old_user_id = created.json()["id"]

        login(old_member_client, old_email, "password123")
        assert old_member_client.get("/api/auth/me").json()["email"] == old_email

        deleted = client.delete(f"/api/admin/users/{old_user_id}")
        assert deleted.status_code == 200, deleted.text
        assert old_member_client.get("/api/auth/me").status_code == 401

        recreated = client.post(
            "/api/admin/users",
            json={
                "email": new_email,
                "display_name": "New Member",
                "password": "password123",
                "role": "member",
            },
        )
        assert recreated.status_code == 200, recreated.text
        assert recreated.json()["id"] != old_user_id
        assert old_member_client.get("/api/auth/me").status_code == 401

        users = client.get("/api/admin/users").json()
        assert old_email not in {user["email"] for user in users}
        assert new_email in {user["email"] for user in users}
    app.dependency_overrides.clear()


def test_disabling_user_revokes_existing_share(tmp_path: Path) -> None:
    email = f"disabled-share-{tmp_path.name}@example.com"
    photo_root = tmp_path / "disabled-share"
    create_photo(photo_root / "shared.jpg")

    client, test_engine = isolated_client(tmp_path)
    member_client = TestClient(app)
    public_client = TestClient(app)
    with client, member_client, public_client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Share Member",
                "password": "password123",
                "role": "member",
            },
        ).json()
        library = client.post("/api/admin/libraries", json={"name": "Share Revoke", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])
        client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": library["id"], "can_view": True, "can_share": True}],
        )
        asset_id = client.get("/api/assets").json()[0]["id"]

        login(member_client, email, "password123")
        share = member_client.post("/api/shares", json={"asset_id": asset_id, "title": "Member Share"})
        assert share.status_code == 200, share.text
        token = share.json()["token"]
        assert public_client.get(f"/api/public/shares/{token}/assets").status_code == 200

        disabled = client.post(f"/api/admin/users/{member['id']}/disable")
        assert disabled.status_code == 200, disabled.text
        assert member_client.get("/api/auth/me").status_code == 401
        assert public_client.get(f"/api/public/shares/{token}/assets").status_code == 404
    app.dependency_overrides.clear()


def test_permission_revocation_deactivates_existing_share(tmp_path: Path) -> None:
    email = f"permission-share-{tmp_path.name}@example.com"
    photo_root = tmp_path / "permission-share"
    create_photo(photo_root / "shared.jpg")

    client, test_engine = isolated_client(tmp_path)
    member_client = TestClient(app)
    public_client = TestClient(app)
    with client, member_client, public_client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Permission Member",
                "password": "password123",
                "role": "member",
            },
        ).json()
        library = client.post("/api/admin/libraries", json={"name": "Permission Revoke", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])
        client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": library["id"], "can_view": True, "can_share": True}],
        )
        asset_id = client.get("/api/assets").json()[0]["id"]

        login(member_client, email, "password123")
        share = member_client.post("/api/shares", json={"asset_id": asset_id, "title": "Permission Share"})
        assert share.status_code == 200, share.text
        token = share.json()["token"]
        assert public_client.get(f"/api/public/shares/{token}/assets").status_code == 200

        permissions = client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": library["id"], "can_view": True, "can_share": False}],
        )
        assert permissions.status_code == 200, permissions.text
        assert public_client.get(f"/api/public/shares/{token}/assets").status_code == 404
    app.dependency_overrides.clear()


def test_admin_can_revoke_member_share(tmp_path: Path) -> None:
    email = f"admin-revoke-share-{tmp_path.name}@example.com"
    photo_root = tmp_path / "admin-revoke-share"
    create_photo(photo_root / "shared.jpg")

    client, test_engine = isolated_client(tmp_path)
    member_client = TestClient(app)
    public_client = TestClient(app)
    with client, member_client, public_client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Revoked Member",
                "password": "password123",
                "role": "member",
            },
        ).json()
        library = client.post("/api/admin/libraries", json={"name": "Admin Revoke", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])
        client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": library["id"], "can_view": True, "can_share": True}],
        )
        asset_id = client.get("/api/assets").json()[0]["id"]

        login(member_client, email, "password123")
        share = member_client.post("/api/shares", json={"asset_id": asset_id, "title": "Admin Revoke Share"})
        assert share.status_code == 200, share.text
        share_id = share.json()["id"]
        token = share.json()["token"]
        assert public_client.get(f"/api/public/shares/{token}/assets").status_code == 200

        revoked = client.delete(f"/api/admin/shares/{share_id}")
        assert revoked.status_code == 200, revoked.text
        assert public_client.get(f"/api/public/shares/{token}/assets").status_code == 404
    app.dependency_overrides.clear()


def test_member_cannot_modify_folder_metadata(tmp_path: Path) -> None:
    email = f"folder-edit-{tmp_path.name}@example.com"
    photo_root = tmp_path / "folder-edit"
    create_photo(photo_root / "one.jpg")

    client, test_engine = isolated_client(tmp_path)
    member_client = TestClient(app)
    with client, member_client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Folder Member",
                "password": "password123",
                "role": "member",
            },
        ).json()
        library = client.post("/api/admin/libraries", json={"name": "Folder Edit", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])
        client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": library["id"], "can_view": True, "can_share": False}],
        )
        folder = next(folder for folder in client.get("/api/folders").json() if folder["library_id"] == library["id"])
        asset_id = client.get(f"/api/assets?folder_id={folder['id']}").json()[0]["id"]

        login(member_client, email, "password123")
        rename = member_client.patch(f"/api/folders/{folder['id']}/rename", json={"name": "Nope"})
        cover = member_client.patch(f"/api/folders/{folder['id']}/cover", json={"cover_asset_id": asset_id})

        assert rename.status_code == 403
        assert cover.status_code == 403
    app.dependency_overrides.clear()


def test_admin_can_set_folder_cover_from_descendant_asset(tmp_path: Path) -> None:
    client, test_engine = isolated_client(tmp_path)
    photo_root = tmp_path / "folder-cover-descendant"
    create_photo(photo_root / "Trips" / "Lake" / "cover.jpg")
    create_photo(photo_root / "Family" / "other.jpg")

    with client:
        login(client, "admin@example.com", "change-me-now")
        library = client.post(
            "/api/admin/libraries",
            json={"name": "Folder Cover Descendant", "path": str(photo_root)},
        ).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])

        root = next(folder for folder in client.get("/api/folders").json() if folder["library_id"] == library["id"])
        children = client.get(f"/api/folders?parent_id={root['id']}").json()
        trips = next(folder for folder in children if folder["name"] == "Trips")
        family = next(folder for folder in children if folder["name"] == "Family")
        lake = next(folder for folder in client.get(f"/api/folders?parent_id={trips['id']}").json() if folder["name"] == "Lake")
        cover_asset_id = client.get(f"/api/assets?folder_id={lake['id']}").json()[0]["id"]
        other_asset_id = client.get(f"/api/assets?folder_id={family['id']}").json()[0]["id"]

        updated = client.patch(f"/api/folders/{trips['id']}/cover", json={"cover_asset_id": cover_asset_id})
        assert updated.status_code == 200, updated.text
        assert updated.json()["cover_asset_id"] == cover_asset_id
        with Session(test_engine) as session:
            scan_library(session, library["id"])
        refreshed = client.get(f"/api/folders/{trips['id']}")
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["cover_asset_id"] == cover_asset_id

        rejected = client.patch(f"/api/folders/{trips['id']}/cover", json={"cover_asset_id": other_asset_id})
        assert rejected.status_code == 400
    app.dependency_overrides.clear()


def test_delete_library_removes_index_and_keeps_original_files(tmp_path: Path) -> None:
    client, test_engine = isolated_client(tmp_path)
    photo_root = tmp_path / "delete-photos"
    original_photo = photo_root / "Trips" / "one.jpg"
    create_photo(original_photo)
    thumbnail_path = settings.thumbnail_dir / "pytest-delete" / f"{tmp_path.name}.webp"

    with client:
        login(client, "admin@example.com", "change-me-now")
        library_response = client.post("/api/admin/libraries", json={"name": "Delete me", "path": str(photo_root)})
        assert library_response.status_code == 200, library_response.text
        library_id = library_response.json()["id"]

        with Session(test_engine) as session:
            scan_library(session, library_id)
            asset = session.exec(select(Asset).where(Asset.library_id == library_id)).first()
            folder = session.exec(select(Folder).where(Folder.library_id == library_id)).first()
            admin = session.exec(select(User).where(User.email == "admin@example.com")).first()
            assert asset is not None
            assert folder is not None
            assert admin is not None
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
            thumbnail_path.write_bytes(b"thumbnail")
            session.add(Thumbnail(asset_id=asset.id or 0, size="small", path=str(thumbnail_path), width=16, height=16))
            session.add(AssetTag(user_id=admin.id or 0, asset_id=asset.id or 0, name="Archive"))
            session.add(LibraryPermission(user_id=admin.id or 0, library_id=library_id, can_view=True, can_share=True))
            session.add(ScanJob(library_id=library_id, status="finished", message="Done"))
            session.add(ShareLink(token=f"asset-{tmp_path.name}", creator_id=admin.id or 0, title="Asset share", asset_id=asset.id))
            session.add(ShareLink(token=f"folder-{tmp_path.name}", creator_id=admin.id or 0, title="Folder share", folder_id=folder.id))
            session.commit()

        delete_response = client.delete(f"/api/admin/libraries/{library_id}")
        assert delete_response.status_code == 200, delete_response.text
        assert delete_response.json() == {"ok": True}

        with Session(test_engine) as session:
            library = session.get(LibraryRoot, library_id)
            assert library is not None
            assert library.deleted_at is not None
            assert library.is_enabled is False
            assert not session.exec(select(LibraryRoot).where(LibraryRoot.id == library_id, LibraryRoot.deleted_at == None)).all()
        assert original_photo.exists()
    app.dependency_overrides.clear()


def test_member_library_access_is_filtered(tmp_path: Path) -> None:
    email = f"filtered-{tmp_path.name}@example.com"
    allowed_root = tmp_path / "allowed"
    blocked_root = tmp_path / "blocked"
    create_photo(allowed_root / "allowed.jpg")
    create_photo(blocked_root / "blocked.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Filtered",
                "password": "password123",
                "role": "member",
            },
        ).json()
        allowed = client.post("/api/admin/libraries", json={"name": f"Allowed {tmp_path.name}", "path": str(allowed_root)}).json()
        blocked = client.post("/api/admin/libraries", json={"name": f"Blocked {tmp_path.name}", "path": str(blocked_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, allowed["id"])
            scan_library(session, blocked["id"])
            session.add(
                LibraryPermission(
                    user_id=member["id"],
                    library_id=allowed["id"],
                    can_view=True,
                    can_share=False,
                )
            )
            session.commit()
        assert filenames(client.get("/api/assets")) == {"allowed.jpg", "blocked.jpg"}

    with client as member_client:
        login(member_client, email, "password123")
        root_folders = member_client.get("/api/folders")
        assert root_folders.status_code == 200
        library_ids = {folder["library_id"] for folder in root_folders.json()}
        assert allowed["id"] in library_ids
        assert blocked["id"] not in library_ids

        blocked_folder_id = next(folder["id"] for folder in root_folders.json() if folder["library_id"] == allowed["id"])
        assets = member_client.get(f"/api/assets?folder_id={blocked_folder_id}")
        assert assets.status_code == 200
        assert filenames(member_client.get("/api/assets")) == {"allowed.jpg"}
        assert {asset["filename"] for asset in member_client.get("/api/assets?search=allowed").json()} == {"allowed.jpg"}
        assert member_client.get("/api/assets?search=blocked").json() == []

        with Session(test_engine) as session:
            blocked_library = session.get(LibraryRoot, blocked["id"])
            assert blocked_library is not None
    app.dependency_overrides.clear()


def test_assets_can_include_subfolder_photos(tmp_path: Path) -> None:
    photo_root = tmp_path / "recursive"
    create_photo(photo_root / "root.jpg")
    create_photo(photo_root / "Nested" / "child.jpg")
    (photo_root / "Nested" / "clip.mp4").parent.mkdir(parents=True, exist_ok=True)
    (photo_root / "Nested" / "clip.mp4").write_bytes(b"indexed video")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        library = client.post("/api/admin/libraries", json={"name": "Recursive", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])

        folder_id = next(folder["id"] for folder in client.get("/api/folders").json() if folder["library_id"] == library["id"])
        direct_assets = client.get(f"/api/assets?folder_id={folder_id}")
        assert direct_assets.status_code == 200, direct_assets.text
        assert {asset["filename"] for asset in direct_assets.json()} == {"root.jpg"}

        recursive_assets = client.get(f"/api/assets?folder_id={folder_id}&recursive=true")
        assert recursive_assets.status_code == 200, recursive_assets.text
        asset_sources = {asset["filename"]: asset for asset in recursive_assets.json()}
        assert set(asset_sources) == {"root.jpg", "child.jpg", "clip.mp4"}
        image_assets = client.get(f"/api/assets?folder_id={folder_id}&recursive=true&media_type=image")
        assert image_assets.status_code == 200, image_assets.text
        assert {asset["filename"] for asset in image_assets.json()} == {"root.jpg", "child.jpg"}
        video_assets = client.get(f"/api/assets?folder_id={folder_id}&recursive=true&media_type=video")
        assert video_assets.status_code == 200, video_assets.text
        assert {asset["filename"] for asset in video_assets.json()} == {"clip.mp4"}
        assert asset_sources["root.jpg"]["library_name"] == "Recursive"
        assert asset_sources["root.jpg"]["folder_name"] == "Recursive"
        assert asset_sources["root.jpg"]["folder_path"] == ""
        assert asset_sources["child.jpg"]["library_name"] == "Recursive"
        assert asset_sources["child.jpg"]["folder_name"] == "Nested"
        assert asset_sources["child.jpg"]["folder_path"] == "Nested"
        assert asset_sources["clip.mp4"]["folder_name"] == "Nested"
        assert asset_sources["clip.mp4"]["mime_type"] == "video/mp4"
    app.dependency_overrides.clear()


def test_assets_can_return_recently_added_photos(tmp_path: Path) -> None:
    photo_root = tmp_path / "recent"
    create_photo(photo_root / "older.jpg")
    create_photo(photo_root / "newer.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        library = client.post("/api/admin/libraries", json={"name": "Recent", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])
            older = session.exec(select(Asset).where(Asset.filename == "older.jpg")).one()
            newer = session.exec(select(Asset).where(Asset.filename == "newer.jpg")).one()
            older.created_at = datetime(2024, 1, 1, 8, 0, 0)
            newer.created_at = datetime(2024, 2, 1, 8, 0, 0)
            session.add(older)
            session.add(newer)
            session.commit()

        recent = client.get("/api/assets?sort=recent&limit=1")
        assert recent.status_code == 200, recent.text
        assert [asset["filename"] for asset in recent.json()] == ["newer.jpg"]
    app.dependency_overrides.clear()


def test_assets_can_filter_photos_with_location(tmp_path: Path) -> None:
    photo_root = tmp_path / "places"
    create_photo(photo_root / "mapped.jpg")
    create_photo(photo_root / "nearby.jpg")
    create_photo(photo_root / "partial.jpg")
    create_photo(photo_root / "plain.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        library = client.post("/api/admin/libraries", json={"name": "Places", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])
            mapped = session.exec(select(Asset).where(Asset.filename == "mapped.jpg")).one()
            nearby = session.exec(select(Asset).where(Asset.filename == "nearby.jpg")).one()
            partial = session.exec(select(Asset).where(Asset.filename == "partial.jpg")).one()
            mapped_id = mapped.id
            nearby_id = nearby.id
            mapped.latitude = 37.8083333
            mapped.longitude = -122.4041667
            mapped.captured_at = datetime(2024, 5, 12, 10, 30)
            nearby.latitude = 37.812
            nearby.longitude = -122.399
            nearby.captured_at = datetime(2024, 5, 13, 10, 30)
            partial.latitude = 37.0
            session.add(mapped)
            session.add(nearby)
            session.add(partial)
            session.commit()

        places = client.get("/api/assets?has_location=true")
        assert places.status_code == 200, places.text
        assert [asset["filename"] for asset in places.json()] == ["mapped.jpg", "nearby.jpg"]
        assert places.json()[0]["latitude"] == 37.8083333
        assert places.json()[0]["longitude"] == -122.4041667
        assert client.get("/api/assets/places").json() == [
            {
                "place_key": "37.81,-122.40",
                "label": "37.81, -122.40",
                "latitude": 37.81,
                "longitude": -122.40,
                "asset_count": 2,
                "cover_asset_id": nearby_id,
                "latest_at": "2024-05-13T10:30:00Z",
            }
        ]
        assert filenames(client.get("/api/assets?place=37.81,-122.40")) == {"mapped.jpg", "nearby.jpg"}
        assert client.get("/api/assets/places?search=mapped").json() == [
            {
                "place_key": "37.81,-122.40",
                "label": "37.81, -122.40",
                "latitude": 37.81,
                "longitude": -122.40,
                "asset_count": 1,
                "cover_asset_id": mapped_id,
                "latest_at": "2024-05-12T10:30:00Z",
            }
        ]
        assert client.get("/api/assets?place=Unknown").json() == []
    app.dependency_overrides.clear()


def test_albums_collect_selected_accessible_photos(tmp_path: Path) -> None:
    photo_root = tmp_path / "albums"
    create_photo(photo_root / "one.jpg")
    create_photo(photo_root / "two.jpg")
    (photo_root / "clip.mp4").write_bytes(b"video")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        library = client.post("/api/admin/libraries", json={"name": "Albums", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])

        assets = client.get("/api/assets").json()
        asset_ids = [asset["id"] for asset in assets]
        image_ids = [asset["id"] for asset in assets if asset["mime_type"].startswith("image/")]
        video_id = next(asset["id"] for asset in assets if asset["mime_type"].startswith("video/"))
        created = client.post("/api/albums", json={"name": " Weekend Picks ", "asset_ids": [image_ids[0], image_ids[0], image_ids[1], video_id]})
        assert created.status_code == 200, created.text
        album = created.json()
        assert album["name"] == "Weekend Picks"
        assert album["asset_count"] == 3
        assert album["cover_asset_id"] == image_ids[0]

        assert [item["id"] for item in client.get("/api/albums").json()] == [album["id"]]
        renamed = client.patch(f"/api/albums/{album['id']}", json={"name": " Edited Picks ", "description": " Best of the weekend "})
        assert renamed.status_code == 200, renamed.text
        album = renamed.json()
        assert album["name"] == "Edited Picks"
        assert album["description"] == "Best of the weekend"
        cover = client.patch(f"/api/albums/{album['id']}/cover", json={"cover_asset_id": image_ids[1]})
        assert cover.status_code == 200, cover.text
        assert cover.json()["cover_asset_id"] == image_ids[1]
        album_tag = client.patch(f"/api/assets/{image_ids[1]}/tags", json={"tags": ["Album Keyword"]})
        assert album_tag.status_code == 200, album_tag.text
        album_assets = client.get(f"/api/albums/{album['id']}/assets")
        assert album_assets.status_code == 200, album_assets.text
        assert {asset["filename"] for asset in album_assets.json()} == {"one.jpg", "two.jpg", "clip.mp4"}
        assert filenames(client.get(f"/api/albums/{album['id']}/assets?search=one")) == {"one.jpg"}
        assert filenames(client.get(f"/api/albums/{album['id']}/assets?search=Album%20Keyword")) == {"two.jpg"}
        assert filenames(client.get(f"/api/albums/{album['id']}/assets?media_type=image")) == {"one.jpg", "two.jpg"}
        assert filenames(client.get(f"/api/albums/{album['id']}/assets?media_type=video")) == {"clip.mp4"}

        appended = client.post(f"/api/albums/{album['id']}/assets", json={"asset_ids": [image_ids[0], image_ids[1], video_id]})
        assert appended.status_code == 200, appended.text
        assert appended.json()["asset_count"] == 3

        removed = client.request("DELETE", f"/api/albums/{album['id']}/assets", json={"asset_ids": [image_ids[0], video_id]})
        assert removed.status_code == 200, removed.text
        assert removed.json()["asset_count"] == 1
        assert removed.json()["cover_asset_id"] == image_ids[1]
        assert {asset["filename"] for asset in client.get(f"/api/albums/{album['id']}/assets").json()} == {"two.jpg"}

        missing_cover = client.patch(f"/api/albums/{album['id']}/cover", json={"cover_asset_id": image_ids[0]})
        assert missing_cover.status_code == 400

        deleted = client.delete(f"/api/albums/{album['id']}")
        assert deleted.status_code == 200, deleted.text
        assert client.get(f"/api/albums/{album['id']}").status_code == 404
    app.dependency_overrides.clear()


def test_album_creation_requires_asset_access_and_is_per_user(tmp_path: Path) -> None:
    email = f"album-member-{tmp_path.name}@example.com"
    allowed_root = tmp_path / "album-allowed"
    blocked_root = tmp_path / "album-blocked"
    create_photo(allowed_root / "allowed.jpg")
    create_photo(blocked_root / "blocked.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Album Member",
                "password": "password123",
                "role": "member",
            },
        ).json()
        allowed = client.post("/api/admin/libraries", json={"name": "Album Allowed", "path": str(allowed_root)}).json()
        blocked = client.post("/api/admin/libraries", json={"name": "Album Blocked", "path": str(blocked_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, allowed["id"])
            scan_library(session, blocked["id"])
        client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": allowed["id"], "can_view": True, "can_share": False}],
        )
        all_assets = client.get("/api/assets").json()
        allowed_asset_id = next(asset["id"] for asset in all_assets if asset["filename"] == "allowed.jpg")
        blocked_asset_id = next(asset["id"] for asset in all_assets if asset["filename"] == "blocked.jpg")

    with client as member_client:
        login(member_client, email, "password123")
        blocked_album = member_client.post("/api/albums", json={"name": "Nope", "asset_ids": [blocked_asset_id]})
        assert blocked_album.status_code == 403

        created = member_client.post("/api/albums", json={"name": "Mine", "asset_ids": [allowed_asset_id]})
        assert created.status_code == 200, created.text
        album_id = created.json()["id"]
        blocked_append = member_client.post(f"/api/albums/{album_id}/assets", json={"asset_ids": [blocked_asset_id]})
        assert blocked_append.status_code == 403
        assert {asset["filename"] for asset in member_client.get(f"/api/albums/{album_id}/assets").json()} == {"allowed.jpg"}

    with client:
        login(client, "admin@example.com", "change-me-now")
        assert client.get(f"/api/albums/{album_id}").status_code == 404
        assert client.patch(f"/api/albums/{album_id}", json={"name": "Admin Edit"}).status_code == 404
    app.dependency_overrides.clear()


def test_asset_search_matches_source_and_metadata(tmp_path: Path) -> None:
    photo_root = tmp_path / "search"
    create_photo(photo_root / "Camera" / "RAW" / "camera.jpg")
    create_photo(photo_root / "Exports" / "edited.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        library = client.post("/api/admin/libraries", json={"name": "Searchable Archive", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])
            camera_asset = session.exec(select(Asset).where(Asset.filename == "camera.jpg")).one()
            camera_asset.camera_make = "Canon"
            camera_asset.camera_model = "EOS R6"
            camera_asset.lens_model = "RF 24-70mm"
            camera_asset.iso = 800
            camera_asset.aperture = "f/2.8"
            camera_asset.exposure_time = "1/125 s"
            camera_asset.focal_length = "50 mm"
            camera_asset.captured_at = datetime(2024, 5, 12, 10, 30, 45)
            session.add(camera_asset)
            session.commit()

        assert filenames(client.get("/api/assets?search=Searchable")) == {"camera.jpg", "edited.jpg"}
        assert filenames(client.get("/api/assets?search=Camera/RAW")) == {"camera.jpg"}
        assert filenames(client.get("/api/assets?search=EOS%20R6")) == {"camera.jpg"}
        assert filenames(client.get("/api/assets?search=RF%2024-70mm")) == {"camera.jpg"}
        assert filenames(client.get("/api/assets?search=800")) == {"camera.jpg"}
        assert filenames(client.get("/api/assets?search=1/125")) == {"camera.jpg"}
        assert filenames(client.get("/api/assets?search=2024-05-12")) == {"camera.jpg"}
        assert client.get("/api/assets/cameras").json() == [
            {"camera_key": "Canon|EOS R6", "label": "Canon EOS R6", "asset_count": 1}
        ]
        assert filenames(client.get("/api/assets?camera=Canon%7CEOS%20R6")) == {"camera.jpg"}
        assert client.get("/api/assets?camera=Canon").json() == []
        assert client.get("/api/assets/lenses").json() == [
            {"lens_key": "RF 24-70mm", "label": "RF 24-70mm", "asset_count": 1}
        ]
        assert filenames(client.get("/api/assets?lens=RF%2024-70mm")) == {"camera.jpg"}
        assert client.get("/api/assets?lens=Unknown").json() == []
    app.dependency_overrides.clear()


def test_asset_download_returns_originals_zip(tmp_path: Path) -> None:
    photo_root = tmp_path / "download"
    create_photo(photo_root / "root.jpg")
    create_photo(photo_root / "Nested" / "child.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        library = client.post("/api/admin/libraries", json={"name": "Download", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])

        folder_id = next(folder["id"] for folder in client.get("/api/folders").json() if folder["library_id"] == library["id"])
        assets = client.get(f"/api/assets?folder_id={folder_id}&recursive=true").json()
        response = client.post("/api/assets/download", json={"asset_ids": [asset["id"] for asset in assets]})

        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/zip"
        assert "dk-photo-originals.zip" in response.headers["content-disposition"]
        with ZipFile(BytesIO(response.content)) as archive:
            assert set(archive.namelist()) == {"root.jpg", "Nested/child.jpg"}
            assert archive.read("root.jpg")
    app.dependency_overrides.clear()


def test_share_links_include_scope_metadata(tmp_path: Path) -> None:
    photo_root = tmp_path / "share-scope"
    create_photo(photo_root / "one.jpg")
    create_photo(photo_root / "two.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        library = client.post("/api/admin/libraries", json={"name": "Share Scope", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])

        folder_id = next(folder["id"] for folder in client.get("/api/folders").json() if folder["library_id"] == library["id"])
        assets = client.get(f"/api/assets?folder_id={folder_id}").json()
        asset_ids = [asset["id"] for asset in assets]

        single = client.post("/api/shares", json={"asset_id": asset_ids[0], "title": "Single"})
        folder = client.post("/api/shares", json={"folder_id": folder_id, "title": "Folder"})
        selected = client.post("/api/shares", json={"asset_ids": asset_ids, "title": "Selected"})
        assert single.status_code == 200, single.text
        assert folder.status_code == 200, folder.text
        assert selected.status_code == 200, selected.text

        assert single.json()["share_kind"] == "asset"
        assert single.json()["asset_count"] == 1
        assert folder.json()["share_kind"] == "folder"
        assert folder.json()["asset_count"] == 2
        assert selected.json()["share_kind"] == "assets"
        assert selected.json()["asset_count"] == 2
        assert selected.json()["asset_ids"] == asset_ids

        own_shares = {share["title"]: share for share in client.get("/api/shares").json()}
        assert own_shares["Single"]["asset_count"] == 1
        assert own_shares["Folder"]["share_kind"] == "folder"
        assert own_shares["Selected"]["asset_count"] == 2

        admin_shares = {share["title"]: share for share in client.get("/api/admin/shares").json()}
        assert admin_shares["Single"]["share_kind"] == "asset"
        assert admin_shares["Folder"]["asset_count"] == 2
        assert admin_shares["Selected"]["share_kind"] == "assets"

        download = client.get(f"/api/public/shares/{selected.json()['token']}/download")
        assert download.status_code == 200, download.text
        assert download.headers["content-type"] == "application/zip"
        assert "dk-photo-share-originals.zip" in download.headers["content-disposition"]
        with ZipFile(BytesIO(download.content)) as archive:
            assert set(archive.namelist()) == {"one.jpg", "two.jpg"}
    app.dependency_overrides.clear()


def test_asset_download_rejects_inaccessible_assets(tmp_path: Path) -> None:
    email = f"download-{tmp_path.name}@example.com"
    allowed_root = tmp_path / "download-allowed"
    blocked_root = tmp_path / "download-blocked"
    create_photo(allowed_root / "allowed.jpg")
    create_photo(blocked_root / "blocked.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Download Member",
                "password": "password123",
                "role": "member",
            },
        ).json()
        allowed = client.post("/api/admin/libraries", json={"name": "Allowed Download", "path": str(allowed_root)}).json()
        blocked = client.post("/api/admin/libraries", json={"name": "Blocked Download", "path": str(blocked_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, allowed["id"])
            scan_library(session, blocked["id"])
        client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": allowed["id"], "can_view": True, "can_share": False}],
        )
        folders = client.get("/api/folders").json()
        allowed_folder_id = next(folder["id"] for folder in folders if folder["library_id"] == allowed["id"])
        blocked_folder_id = next(folder["id"] for folder in folders if folder["library_id"] == blocked["id"])
        allowed_asset_id = client.get(f"/api/assets?folder_id={allowed_folder_id}").json()[0]["id"]
        blocked_asset_id = client.get(f"/api/assets?folder_id={blocked_folder_id}").json()[0]["id"]

    with client as member_client:
        login(member_client, email, "password123")
        allowed_download = member_client.post("/api/assets/download", json={"asset_ids": [allowed_asset_id]})
        assert allowed_download.status_code == 200, allowed_download.text

        blocked_download = member_client.post("/api/assets/download", json={"asset_ids": [allowed_asset_id, blocked_asset_id]})
        assert blocked_download.status_code == 403
    app.dependency_overrides.clear()


def test_asset_favorites_are_per_user_and_filterable(tmp_path: Path) -> None:
    email = f"favorite-{tmp_path.name}@example.com"
    photo_root = tmp_path / "favorites"
    create_photo(photo_root / "one.jpg")
    create_photo(photo_root / "two.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Favorite Member",
                "password": "password123",
                "role": "member",
            },
        ).json()
        library = client.post("/api/admin/libraries", json={"name": "Favorites", "path": str(photo_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, library["id"])
        client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": library["id"], "can_view": True, "can_share": False}],
        )

        folder_id = next(folder["id"] for folder in client.get("/api/folders").json() if folder["library_id"] == library["id"])
        assets = client.get(f"/api/assets?folder_id={folder_id}").json()
        asset_id = assets[0]["id"]
        assert assets[0]["is_favorite"] is False

        favorite = client.patch(f"/api/assets/{asset_id}/favorite", json={"is_favorite": True})
        assert favorite.status_code == 200, favorite.text
        assert favorite.json()["is_favorite"] is True
        admin_favorites = client.get(f"/api/assets?folder_id={folder_id}&favorites_only=true")
        assert [asset["id"] for asset in admin_favorites.json()] == [asset_id]
        admin_global_favorites = client.get("/api/assets?favorites_only=true")
        assert [asset["id"] for asset in admin_global_favorites.json()] == [asset_id]

    with client as member_client:
        login(member_client, email, "password123")
        member_assets = member_client.get(f"/api/assets?folder_id={folder_id}")
        assert member_assets.status_code == 200
        assert next(asset for asset in member_assets.json() if asset["id"] == asset_id)["is_favorite"] is False
        assert member_client.get(f"/api/assets?folder_id={folder_id}&favorites_only=true").json() == []
        assert member_client.get("/api/assets?favorites_only=true").json() == []

        member_favorite = member_client.patch(f"/api/assets/{asset_id}/favorite", json={"is_favorite": True})
        assert member_favorite.status_code == 200, member_favorite.text
        assert member_favorite.json()["is_favorite"] is True
        member_favorites = member_client.get(f"/api/assets?folder_id={folder_id}&favorites_only=true")
        assert [asset["id"] for asset in member_favorites.json()] == [asset_id]
        member_global_favorites = member_client.get("/api/assets?favorites_only=true")
        assert [asset["id"] for asset in member_global_favorites.json()] == [asset_id]
    app.dependency_overrides.clear()


def test_asset_metadata_is_per_user_searchable_and_filterable(tmp_path: Path) -> None:
    email = f"metadata-{tmp_path.name}@example.com"
    allowed_root = tmp_path / "metadata-allowed"
    blocked_root = tmp_path / "metadata-blocked"
    create_photo(allowed_root / "keeper.jpg")
    create_photo(allowed_root / "plain.jpg")
    create_photo(blocked_root / "hidden.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Metadata Member",
                "password": "password123",
                "role": "member",
            },
        ).json()
        allowed = client.post("/api/admin/libraries", json={"name": "Metadata Allowed", "path": str(allowed_root)}).json()
        blocked = client.post("/api/admin/libraries", json={"name": "Metadata Blocked", "path": str(blocked_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, allowed["id"])
            scan_library(session, blocked["id"])
        client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": allowed["id"], "can_view": True, "can_share": False}],
        )

        assets = client.get("/api/assets").json()
        keeper_id = next(asset["id"] for asset in assets if asset["filename"] == "keeper.jpg")
        plain_id = next(asset["id"] for asset in assets if asset["filename"] == "plain.jpg")
        hidden_id = next(asset["id"] for asset in assets if asset["filename"] == "hidden.jpg")
        assert next(asset for asset in assets if asset["id"] == keeper_id)["rating"] == 0
        update = client.patch(
            f"/api/assets/{keeper_id}/metadata",
            json={"description": "  Portfolio keeper  ", "rating": 4},
        )
        assert update.status_code == 200, update.text
        assert update.json()["description"] == "Portfolio keeper"
        assert update.json()["rating"] == 4
        assert client.patch(f"/api/assets/{plain_id}/metadata", json={"description": "", "rating": 2}).status_code == 200
        assert client.patch(f"/api/assets/{hidden_id}/metadata", json={"description": "Admin hidden", "rating": 5}).status_code == 200
        assert {rating["rating"]: rating["asset_count"] for rating in client.get("/api/assets/ratings").json()} == {
            1: 3,
            2: 3,
            3: 2,
            4: 2,
            5: 1,
        }
        assert filenames(client.get("/api/assets?search=Portfolio")) == {"keeper.jpg"}
        assert filenames(client.get("/api/assets?min_rating=3")) == {"hidden.jpg", "keeper.jpg"}

    with client as member_client:
        login(member_client, email, "password123")
        assert member_client.get(f"/api/assets/{keeper_id}").json()["rating"] == 0
        assert member_client.get("/api/assets?search=Portfolio").json() == []
        assert member_client.get("/api/assets?min_rating=3").json() == []
        assert {rating["rating"]: rating["asset_count"] for rating in member_client.get("/api/assets/ratings").json()} == {
            1: 0,
            2: 0,
            3: 0,
            4: 0,
            5: 0,
        }
        assert member_client.patch(f"/api/assets/{hidden_id}/metadata", json={"description": "Nope", "rating": 5}).status_code == 403

        member_update = member_client.patch(
            f"/api/assets/{keeper_id}/metadata",
            json={"description": "Member portfolio", "rating": 5},
        )
        assert member_update.status_code == 200, member_update.text
        assert member_update.json()["description"] == "Member portfolio"
        assert member_update.json()["rating"] == 5
        assert filenames(member_client.get("/api/assets?search=Member%20portfolio")) == {"keeper.jpg"}
        assert filenames(member_client.get("/api/assets?min_rating=5")) == {"keeper.jpg"}
        assert filenames(member_client.get("/api/assets?min_rating=3")) == {"keeper.jpg"}
        assert {rating["rating"]: rating["asset_count"] for rating in member_client.get("/api/assets/ratings").json()} == {
            1: 1,
            2: 1,
            3: 1,
            4: 1,
            5: 1,
        }
        clear = member_client.patch(f"/api/assets/{keeper_id}/metadata", json={"description": "", "rating": 0})
        assert clear.status_code == 200, clear.text
        assert clear.json()["description"] == ""
        assert clear.json()["rating"] == 0
        assert member_client.get("/api/assets?min_rating=1").json() == []
        assert {rating["rating"]: rating["asset_count"] for rating in member_client.get("/api/assets/ratings").json()} == {
            1: 0,
            2: 0,
            3: 0,
            4: 0,
            5: 0,
        }

    with client:
        login(client, "admin@example.com", "change-me-now")
        assert client.get(f"/api/assets/{keeper_id}").json()["rating"] == 4
        assert filenames(client.get("/api/assets?min_rating=5")) == {"hidden.jpg"}
        delete_library = client.delete(f"/api/admin/libraries/{allowed['id']}")
        assert delete_library.status_code == 200, delete_library.text
        with Session(test_engine) as session:
            library = session.get(LibraryRoot, allowed["id"])
            assert library is not None
            assert library.deleted_at is not None
            assert library.is_enabled is False
            assert session.exec(select(AssetMetadata).where(AssetMetadata.asset_id == hidden_id)).one().rating == 5

    app.dependency_overrides.clear()


def test_asset_tags_are_per_user_filterable_and_permission_scoped(tmp_path: Path) -> None:
    email = f"tag-member-{tmp_path.name}@example.com"
    allowed_root = tmp_path / "tag-allowed"
    blocked_root = tmp_path / "tag-blocked"
    create_photo(allowed_root / "allowed.jpg")
    create_photo(allowed_root / "second.jpg")
    create_photo(blocked_root / "blocked.jpg")

    client, test_engine = isolated_client(tmp_path)
    with client:
        login(client, "admin@example.com", "change-me-now")
        member = client.post(
            "/api/admin/users",
            json={
                "email": email,
                "display_name": "Tag Member",
                "password": "password123",
                "role": "member",
            },
        ).json()
        allowed = client.post("/api/admin/libraries", json={"name": "Tag Allowed", "path": str(allowed_root)}).json()
        blocked = client.post("/api/admin/libraries", json={"name": "Tag Blocked", "path": str(blocked_root)}).json()
        with Session(test_engine) as session:
            scan_library(session, allowed["id"])
            scan_library(session, blocked["id"])
        client.put(
            f"/api/admin/users/{member['id']}/permissions",
            json=[{"library_id": allowed["id"], "can_view": True, "can_share": False}],
        )

        assets = client.get("/api/assets").json()
        allowed_asset_id = next(asset["id"] for asset in assets if asset["filename"] == "allowed.jpg")
        blocked_asset_id = next(asset["id"] for asset in assets if asset["filename"] == "blocked.jpg")
        admin_tags = client.patch(
            f"/api/assets/{allowed_asset_id}/tags",
            json={"tags": [" Travel ", "travel", "Family  Trip", "", "Kids Photos"]},
        )
        assert admin_tags.status_code == 200, admin_tags.text
        assert admin_tags.json()["tags"] == ["Family Trip", "Kids Photos", "Travel"]
        assert client.patch(f"/api/assets/{blocked_asset_id}/tags", json={"tags": ["Travel"]}).status_code == 200
        assert filenames(client.get("/api/assets?tag=Travel")) == {"allowed.jpg", "blocked.jpg"}
        assert filenames(client.get("/api/assets?search=Kids%20Photos")) == {"allowed.jpg"}
        assert {tag["name"]: tag["asset_count"] for tag in client.get("/api/assets/tags").json()} == {
            "Family Trip": 1,
            "Kids Photos": 1,
            "Travel": 2,
        }

        with Session(test_engine) as session:
            session.add(AssetTag(user_id=member["id"], asset_id=blocked_asset_id, name="Hidden"))
            session.commit()

    with client as member_client:
        login(member_client, email, "password123")
        assert member_client.get(f"/api/assets/{allowed_asset_id}").json()["tags"] == []
        assert member_client.get("/api/assets?search=Kids%20Photos").json() == []
        assert member_client.patch(f"/api/assets/{blocked_asset_id}/tags", json={"tags": ["Hidden"]}).status_code == 403

        member_tags = member_client.patch(
            f"/api/assets/{allowed_asset_id}/tags",
            json={"tags": [" Travel ", "Member Tag", "travel"]},
        )
        assert member_tags.status_code == 200, member_tags.text
        assert member_tags.json()["tags"] == ["Member Tag", "Travel"]
        assert filenames(member_client.get("/api/assets?search=Member%20Tag")) == {"allowed.jpg"}
        bulk_member_tags = member_client.post(
            "/api/assets/bulk-tags",
            json={"asset_ids": [allowed_asset_id], "tags": ["Member Tag", "Family  Trip"]},
        )
        assert bulk_member_tags.status_code == 200, bulk_member_tags.text
        assert bulk_member_tags.json()[0]["tags"] == ["Family Trip", "Member Tag", "Travel"]
        assert member_client.post(
            "/api/assets/bulk-tags",
            json={"asset_ids": [blocked_asset_id], "tags": ["Hidden"]},
        ).status_code == 403
        assert filenames(member_client.get("/api/assets?tag=Travel")) == {"allowed.jpg"}
        assert member_client.get("/api/assets?tag=Hidden").json() == []
        assert {tag["name"]: tag["asset_count"] for tag in member_client.get("/api/assets/tags").json()} == {
            "Family Trip": 1,
            "Member Tag": 1,
            "Travel": 1,
        }
        rename_member_tag = member_client.patch("/api/assets/tags/Family%20Trip", json={"name": "Travel"})
        assert rename_member_tag.status_code == 200, rename_member_tag.text
        assert rename_member_tag.json() == {"name": "Travel", "asset_count": 1}
        assert member_client.get(f"/api/assets/{allowed_asset_id}").json()["tags"] == ["Member Tag", "Travel"]
        remove_member_tags = member_client.post(
            "/api/assets/bulk-tags/remove",
            json={"asset_ids": [allowed_asset_id], "tags": ["Travel"]},
        )
        assert remove_member_tags.status_code == 200, remove_member_tags.text
        assert remove_member_tags.json()[0]["tags"] == ["Member Tag"]
        assert member_client.get("/api/assets?tag=Travel").json() == []
        assert member_client.post(
            "/api/assets/bulk-tags/remove",
            json={"asset_ids": [blocked_asset_id], "tags": ["Hidden"]},
        ).status_code == 403
        assert member_client.delete("/api/assets/tags/Hidden").status_code == 404
        assert member_client.delete("/api/assets/tags/Member%20Tag").status_code == 200
        assert member_client.get(f"/api/assets/{allowed_asset_id}").json()["tags"] == []

    with client:
        login(client, "admin@example.com", "change-me-now")
        bulk_admin_tags = client.post(
            "/api/assets/bulk-tags",
            json={"asset_ids": [allowed_asset_id, blocked_asset_id], "tags": ["Travel", "Archive"]},
        )
        assert bulk_admin_tags.status_code == 200, bulk_admin_tags.text
        assert [asset["filename"] for asset in bulk_admin_tags.json()] == ["allowed.jpg", "blocked.jpg"]
        assert set(client.get(f"/api/assets/{allowed_asset_id}").json()["tags"]) == {"Archive", "Family Trip", "Kids Photos", "Travel"}
        assert set(client.get(f"/api/assets/{blocked_asset_id}").json()["tags"]) == {"Archive", "Travel"}
        remove_admin_tags = client.post(
            "/api/assets/bulk-tags/remove",
            json={"asset_ids": [allowed_asset_id], "tags": ["Travel"]},
        )
        assert remove_admin_tags.status_code == 200, remove_admin_tags.text
        assert set(remove_admin_tags.json()[0]["tags"]) == {"Archive", "Family Trip", "Kids Photos"}
        assert filenames(client.get("/api/assets?tag=Travel")) == {"blocked.jpg"}
        rename_admin_tag = client.patch("/api/assets/tags/Archive", json={"name": "Stored"})
        assert rename_admin_tag.status_code == 200, rename_admin_tag.text
        assert rename_admin_tag.json() == {"name": "Stored", "asset_count": 2}
        assert filenames(client.get("/api/assets?tag=Stored")) == {"allowed.jpg", "blocked.jpg"}
        assert client.delete("/api/assets/tags/Stored").status_code == 200
        assert filenames(client.get("/api/assets?tag=Stored")) == set()
    app.dependency_overrides.clear()
