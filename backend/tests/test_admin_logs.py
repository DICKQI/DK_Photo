from __future__ import annotations

import json
import logging
import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app import logger
from app.api import admin as admin_api
from app.db import get_session
from app.main import app
from app.models import User
from app.security import hash_password


def isolated_client(tmp_path: Path) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'admin-logs.sqlite3'}", connect_args={"check_same_thread": False})
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
    return TestClient(app)


def login(client: TestClient, email: str) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": "change-me-now"})
    assert response.status_code == 200, response.text


async def read_event_blocks(count: int, tail: int = 200, after: int | None = None) -> list[list[str]]:
    queue = logger.subscribe()
    events = admin_api._log_stream_events(queue, tail=tail, after=after)
    blocks: list[list[str]] = []
    try:
        async for event in events:
            blocks.append(event.rstrip("\n").splitlines())
            if len(blocks) >= count:
                break
    finally:
        await events.aclose()
    return blocks


def event_payload(block: list[str]) -> dict:
    data_line = next(line for line in block if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))


def test_log_stream_requires_admin(tmp_path: Path) -> None:
    logger._reset_for_tests()
    client = isolated_client(tmp_path)
    try:
        with client:
            assert client.get("/api/admin/logs/stream").status_code == 401

            login(client, "member@example.com")
            assert client.get("/api/admin/logs/stream").status_code == 403
    finally:
        app.dependency_overrides.clear()
        logger._reset_for_tests()


def test_log_stream_starts_with_ready_event_before_replayed_logs(tmp_path: Path) -> None:
    logger._reset_for_tests()
    client = isolated_client(tmp_path)
    try:
        with client:
            login(client, "admin@example.com")
            logging.getLogger("tests.admin_logs").info("existing log")

            blocks = asyncio.run(read_event_blocks(2, tail=1))

            assert blocks[0] == ["event: ready", 'data: {"connected":true}']
            assert "id: " in blocks[1][0]
            assert event_payload(blocks[1])["message"] == "existing log"
    finally:
        app.dependency_overrides.clear()
        logger._reset_for_tests()


def test_log_stream_replays_tail_and_after_with_event_ids(tmp_path: Path) -> None:
    logger._reset_for_tests()
    client = isolated_client(tmp_path)
    try:
        with client:
            login(client, "admin@example.com")
            log = logging.getLogger("tests.admin_logs")
            log.info("first")
            log.info("second")
            log.info("third")
            first_id = logger.get_recent(tail=1, after=None)[0].id - 2

            blocks = asyncio.run(read_event_blocks(3, tail=3, after=first_id))

            replayed = [event_payload(block)["message"] for block in blocks[1:]]
            ids = [int(next(line for line in block if line.startswith("id: ")).removeprefix("id: ")) for block in blocks[1:]]
            assert replayed == ["second", "third"]
            assert ids == sorted(ids)
            assert all(log_id > first_id for log_id in ids)
    finally:
        app.dependency_overrides.clear()
        logger._reset_for_tests()


def test_setup_logging_is_idempotent() -> None:
    logger._reset_for_tests()
    try:
        logger.setup_logging()
        logger.setup_logging()

        logging.getLogger("tests.admin_logs").info("single entry")

        entries = [entry for entry in logger.get_recent(tail=10, after=None) if entry.message == "single entry"]
        assert len(entries) == 1
    finally:
        logger._reset_for_tests()
