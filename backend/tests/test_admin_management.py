from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.models import LibraryPermission, LibraryRoot
from app.security import hash_password
from app.services.scanner import scan_library


def create_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "#3b82f6").save(path)


def login(client: TestClient, email: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


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


def test_admin_filesystem_requires_auth(tmp_path: Path) -> None:
    client, _ = isolated_client(tmp_path)
    with client:
        response = client.get("/api/admin/filesystem/roots")
        assert response.status_code == 401
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

        with Session(test_engine) as session:
            blocked_library = session.get(LibraryRoot, blocked["id"])
            assert blocked_library is not None
    app.dependency_overrides.clear()
