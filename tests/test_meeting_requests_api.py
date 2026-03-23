import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import aiosqlite
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.meeting_requests import router as meeting_requests_router
from backend.app.db import get_db
from backend.app.settings import settings


def _build_app(db_path: Path) -> FastAPI:
    app = FastAPI()
    app.include_router(meeting_requests_router, prefix="/api")

    async def _db_override() -> AsyncGenerator[aiosqlite.Connection, None]:
        db = await aiosqlite.connect(str(db_path))
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        try:
            yield db
        finally:
            await db.close()

    app.dependency_overrides[get_db] = _db_override
    return app


def _prepare_db(db_path: Path) -> None:
    async def _init() -> None:
        async with aiosqlite.connect(str(db_path)) as db:
            await db.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_id INTEGER UNIQUE NOT NULL,
                    source TEXT,
                    tg_username TEXT,
                    full_name TEXT,
                    role TEXT,
                    is_admin INTEGER DEFAULT 0,
                    status TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
                CREATE TABLE meeting_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER NOT NULL,
                    to_user_id INTEGER NOT NULL,
                    scheduled_for TEXT,
                    format TEXT,
                    location TEXT,
                    message TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    expires_at TEXT,
                    responder_user_id INTEGER,
                    responded_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK(from_user_id != to_user_id),
                    FOREIGN KEY(from_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(to_user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(responder_user_id) REFERENCES users(id) ON DELETE SET NULL
                );
                """
            )
            await db.execute(
                """
                INSERT INTO users (
                    id, tg_id, source, tg_username, full_name, role, is_admin, status, created_at, updated_at
                ) VALUES
                    (2, 900000002, 'sample', 'user2', 'User 2', 'member', 0, 'active', datetime('now'), datetime('now')),
                    (3, 900000003, 'sample', 'user3', 'User 3', 'member', 0, 'active', datetime('now'), datetime('now'))
                """
            )
            await db.commit()

    asyncio.run(_init())


def test_meeting_request_dev_success(tmp_path: Path) -> None:
    db_path = tmp_path / "meeting_request_dev_success.sqlite3"
    _prepare_db(db_path)

    old_env = settings.env
    old_dev_enabled = settings.dev_auth_enabled
    old_dev_user_id = settings.dev_auth_user_id
    object.__setattr__(settings, "env", "dev")
    object.__setattr__(settings, "dev_auth_enabled", True)
    object.__setattr__(settings, "dev_auth_user_id", 1)

    app = _build_app(db_path)
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/meeting-requests",
                json={
                    "to_user_id": 2,
                    "proposed_time": "2026-03-10T14:30",
                    "format": "online",
                    "message": "test",
                },
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["ok"] is True
            assert body["request"]["from_user_id"] == 1
            assert body["request"]["to_user_id"] == 2
            assert body["request"]["status"] == "pending"
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)


def test_meeting_request_self_invite_returns_400(tmp_path: Path) -> None:
    db_path = tmp_path / "meeting_request_self.sqlite3"
    _prepare_db(db_path)

    old_env = settings.env
    old_dev_enabled = settings.dev_auth_enabled
    old_dev_user_id = settings.dev_auth_user_id
    object.__setattr__(settings, "env", "dev")
    object.__setattr__(settings, "dev_auth_enabled", True)
    object.__setattr__(settings, "dev_auth_user_id", 1)

    app = _build_app(db_path)
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/meeting-requests",
                json={
                    "to_user_id": 1,
                    "proposed_time": "2026-03-10T14:30",
                    "format": "online",
                    "message": "self",
                },
            )
            assert resp.status_code == 400
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)


def test_meeting_request_duplicate_active_returns_409(tmp_path: Path) -> None:
    db_path = tmp_path / "meeting_request_duplicate.sqlite3"
    _prepare_db(db_path)

    old_env = settings.env
    old_dev_enabled = settings.dev_auth_enabled
    old_dev_user_id = settings.dev_auth_user_id
    object.__setattr__(settings, "env", "dev")
    object.__setattr__(settings, "dev_auth_enabled", True)
    object.__setattr__(settings, "dev_auth_user_id", 1)

    app = _build_app(db_path)
    try:
        with TestClient(app) as client:
            payload = {
                "to_user_id": 2,
                "proposed_time": "2026-03-10T14:30",
                "format": "offline",
                "message": "dup",
            }
            first = client.post("/api/meeting-requests", json=payload)
            assert first.status_code == 200

            second = client.post("/api/meeting-requests", json=payload)
            assert second.status_code == 409
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)


def test_meeting_request_prod_without_auth_returns_401(tmp_path: Path) -> None:
    db_path = tmp_path / "meeting_request_prod_auth.sqlite3"
    _prepare_db(db_path)

    old_env = settings.env
    old_dev_enabled = settings.dev_auth_enabled
    old_dev_user_id = settings.dev_auth_user_id
    object.__setattr__(settings, "env", "prod")
    object.__setattr__(settings, "dev_auth_enabled", False)
    object.__setattr__(settings, "dev_auth_user_id", 1)

    app = _build_app(db_path)
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/meeting-requests",
                json={
                    "to_user_id": 2,
                    "proposed_time": "2026-03-10T14:30",
                    "format": "online",
                    "message": "test",
                },
            )
            assert resp.status_code == 401
            assert resp.json().get("detail") == "Not authenticated"
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)
