import asyncio
from collections.abc import AsyncGenerator

import aiosqlite
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.deps import get_current_user
from backend.app.api.routes import lightning as lightning_route
from backend.app.db import get_db
from backend.app.settings import settings


async def _init_seed_schema(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                source TEXT DEFAULT 'real',
                tg_username TEXT,
                full_name TEXT,
                role TEXT DEFAULT 'member',
                is_admin INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
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
                updated_at TEXT NOT NULL
            );
            CREATE TABLE meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                initiator_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                request_id INTEGER UNIQUE,
                participant_a_id INTEGER,
                participant_b_id INTEGER,
                scheduled_for TEXT,
                format TEXT,
                location TEXT,
                notes TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                confirmed_at TEXT,
                completed_at TEXT,
                cancelled_at TEXT
            );
            CREATE TABLE meeting_confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                confirmation_status TEXT NOT NULL,
                comment TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(meeting_id, user_id)
            );
            CREATE TABLE points_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                reason_type TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                meta TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        await db.execute(
            "INSERT INTO users (id, tg_id, full_name, role, is_admin, status) VALUES (1, 900000001, 'Maydan', 'member', 0, 'active')"
        )
        await db.execute(
            "INSERT INTO users (id, tg_id, full_name, role, is_admin, status) VALUES (2, 900000002, 'Aidar Bekov', 'member', 0, 'active')"
        )
        await db.execute(
            "INSERT INTO users (id, tg_id, full_name, role, is_admin, status) VALUES (3, 900000003, 'Alina Seitova', 'member', 0, 'active')"
        )
        await db.execute(
            "INSERT INTO users (id, tg_id, full_name, role, is_admin, status) VALUES (4, 900000004, 'Nursultan Ibraev', 'member', 0, 'active')"
        )
        await db.commit()


def _build_app(db_path: str) -> FastAPI:
    app = FastAPI()
    app.include_router(lightning_route.router, prefix="/api")

    async def _db_override() -> AsyncGenerator[aiosqlite.Connection, None]:
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        try:
            yield db
        finally:
            await db.close()

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "role": "member", "is_admin": 0}
    return app


def test_seed_one_on_one_requests_endpoint_counts(tmp_path) -> None:
    db_path = str(tmp_path / "seed.sqlite3")
    asyncio.run(_init_seed_schema(db_path))

    old_env = settings.env
    old_dev = settings.dev_auth_enabled
    object.__setattr__(settings, "env", "dev")
    object.__setattr__(settings, "dev_auth_enabled", True)
    try:
        app = _build_app(db_path)
        with TestClient(app) as client:
            first_seed = client.post("/api/lightning/dev/seed-one-on-one?user_id=1")
            assert first_seed.status_code == 200
            first_body = first_seed.json()
            assert first_body["ok"] is True
            assert first_body["counts"]["outgoing_requests"] == 2
            assert first_body["counts"]["incoming_requests"] == 1

            second_seed = client.post("/api/lightning/dev/seed-one-on-one?user_id=1")
            assert second_seed.status_code == 200
            second_body = second_seed.json()
            assert second_body["counts"]["outgoing_requests"] == 2
            assert second_body["counts"]["incoming_requests"] == 1

            outgoing = client.get("/api/lightning/requests?type=outgoing")
            assert outgoing.status_code == 200
            outgoing_body = outgoing.json()
            assert outgoing_body["count"] == 2

            incoming = client.get("/api/lightning/requests?type=incoming")
            assert incoming.status_code == 200
            incoming_body = incoming.json()
            assert incoming_body["count"] == 1
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev)
