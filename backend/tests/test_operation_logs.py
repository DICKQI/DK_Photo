from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, SQLModel, create_engine

from app import logger
from app.db import get_session
from app.main import app
from app.models import User
from app.security import hash_password
from app.services.operation_log import log_operation
from app.services.scanner import run_scan_job


def isolated_client(tmp_path: Path) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'operation-logs.sqlite3'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            User(
                email="admin@example.com",
                display_name="Administrator",
                role="admin",
                password_hash=hash_password("change-me-now"),
            )
        )
        session.add(
            User(
                email="member@example.com",
                display_name="Member",
                role="member",
                password_hash=hash_password("change-me-now"),
            )
        )
        session.commit()

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    client.operation_log_test_engine = engine  # type: ignore[attr-defined]
    return client


def login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "change-me-now"})
    assert response.status_code == 200, response.text


def create_photo(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "#3b82f6").save(path)


def setup_test_logging(log_path: Path) -> None:
    logger._reset_for_tests()
    logger.setup_logging(log_path=log_path)


def recent_messages() -> str:
    return "\n".join(json.dumps(entry.model_dump(), ensure_ascii=False) for entry in logger.get_recent(tail=200))


def test_operation_log_records_structured_fields_and_redacts_sensitive_metadata(tmp_path: Path) -> None:
    log_path = tmp_path / "app.jsonl"
    setup_test_logging(log_path)
    try:
        log_operation(
            action="user.login",
            category="audit",
            status="success",
            actor_id=7,
            target_type="user",
            target_id="7",
            message="User login succeeded",
            metadata={"safe": "visible", "password": "secret-password", "nested": {"token": "secret-token"}},
        )

        entry = logger.get_recent(tail=1)[0]
        assert entry.category == "audit"
        assert entry.action == "user.login"
        assert entry.status == "success"
        assert entry.actor_id == 7
        assert entry.target_type == "user"
        assert entry.target_id == "7"
        assert entry.metadata == {
            "safe": "visible",
            "password": "[REDACTED]",
            "nested": {"token": "[REDACTED]"},
        }
        persisted = log_path.read_text(encoding="utf-8")
        assert "secret-password" not in persisted
        assert "secret-token" not in persisted
        assert "user.login" in persisted
    finally:
        logger._reset_for_tests()


def test_request_logging_middleware_logs_success_and_redacts_login_password(tmp_path: Path) -> None:
    log_path = tmp_path / "app.jsonl"
    setup_test_logging(log_path)
    client = isolated_client(tmp_path)
    try:
        with client:
            assert client.get("/api/health").status_code == 200
            assert client.post(
                "/api/auth/login",
                json={"email": "missing@example.com", "password": "secret-password"},
            ).status_code == 401

        messages = recent_messages()
        assert '"category": "request"' in messages
        assert '"action": "http.request"' in messages
        assert '"/api/health"' in messages
        assert '"/api/auth/login"' in messages
        assert "secret-password" not in messages
    finally:
        app.dependency_overrides.clear()
        logger._reset_for_tests()


def test_log_history_endpoint_filters_and_paginates_persisted_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "app.jsonl"
    setup_test_logging(log_path)
    client = isolated_client(tmp_path)
    try:
        with client:
            login(client)
            log_operation(action="library.created", category="audit", status="success", message="Created family library")
            log_operation(action="scan.completed", category="task", status="success", message="Scan completed")

            response = client.get("/api/admin/logs/history?limit=1&category=audit&search=family")

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["next_cursor"] is None
        assert len(data["items"]) == 1
        assert data["items"][0]["action"] == "library.created"
        assert data["items"][0]["category"] == "audit"
    finally:
        app.dependency_overrides.clear()
        logger._reset_for_tests()


def test_admin_business_operations_emit_audit_logs(tmp_path: Path) -> None:
    log_path = tmp_path / "app.jsonl"
    setup_test_logging(log_path)
    client = isolated_client(tmp_path)
    photo_root = tmp_path / "photos"
    photo_root.mkdir()
    try:
        with client:
            login(client)
            library = client.post(
                "/api/admin/libraries",
                json={"name": "Family", "path": str(photo_root), "watch_enabled": False},
            )
            assert library.status_code == 200, library.text
            library_id = library.json()["id"]

            created_user = client.post(
                "/api/admin/users",
                json={
                    "email": "member2@example.com",
                    "display_name": "Member Two",
                    "password": "member-pass-123",
                    "role": "member",
                },
            )
            assert created_user.status_code == 200, created_user.text
            user_id = created_user.json()["id"]

            permissions = client.put(
                f"/api/admin/users/{user_id}/permissions",
                json=[{"library_id": library_id, "can_view": True, "can_share": True}],
            )
            assert permissions.status_code == 200, permissions.text
            assert client.put("/api/admin/settings", json={"thumb_workers": 1}).status_code == 200
            assert client.delete("/api/admin/processing-errors").status_code == 200

        actions = {entry.action for entry in logger.get_recent(tail=200)}
        assert {
            "library.create",
            "user.create",
            "user.permissions.update",
            "settings.update",
            "processing_errors.clear",
        }.issubset(actions)
        assert "member-pass-123" not in recent_messages()
    finally:
        app.dependency_overrides.clear()
        logger._reset_for_tests()


def test_content_operations_emit_audit_logs(tmp_path: Path) -> None:
    log_path = tmp_path / "app.jsonl"
    setup_test_logging(log_path)
    client = isolated_client(tmp_path)
    photo_root = tmp_path / "photos"
    create_photo(photo_root / "one.jpg")
    try:
        with client:
            login(client)
            library = client.post(
                "/api/admin/libraries",
                json={"name": "Family", "path": str(photo_root), "watch_enabled": False},
            )
            assert library.status_code == 200, library.text
            library_id = library.json()["id"]
            scan = client.post(f"/api/admin/libraries/{library_id}/scan")
            assert scan.status_code == 200, scan.text
            with Session(client.operation_log_test_engine) as session:  # type: ignore[attr-defined]
                run_scan_job(session, scan.json()["id"], generate_thumbnails=False)
            assets = client.get("/api/assets").json()
            assert len(assets) == 1
            asset_id = assets[0]["id"]

            album = client.post("/api/albums", json={"name": "Trip", "description": "", "asset_ids": [asset_id]})
            assert album.status_code == 200, album.text
            album_id = album.json()["id"]
            assert client.patch(f"/api/albums/{album_id}", json={"name": "Trip edited"}).status_code == 200
            assert client.patch(f"/api/assets/{asset_id}/favorite", json={"is_favorite": True}).status_code == 200
            assert client.patch(
                f"/api/assets/{asset_id}/metadata",
                json={"description": "Keeper", "rating": 5},
            ).status_code == 200
            assert client.patch(f"/api/assets/{asset_id}/tags", json={"tags": ["Travel"]}).status_code == 200
            share = client.post("/api/shares", json={"asset_id": asset_id, "title": "Share one"})
            assert share.status_code == 200, share.text

        actions = {entry.action for entry in logger.get_recent(tail=400)}
        assert {
            "scan.queued",
            "scan.completed",
            "album.create",
            "album.update",
            "asset.favorite.update",
            "asset.metadata.update",
            "asset.tags.update",
            "share.create",
        }.issubset(actions)
    finally:
        app.dependency_overrides.clear()
        logger._reset_for_tests()
