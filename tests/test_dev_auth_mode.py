from collections.abc import AsyncGenerator
from pathlib import Path

import aiosqlite
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.me import router as me_router
from backend.app.db import USERS_TABLE_SQL, get_db
from backend.app.settings import settings


def _build_app(db_path: Path) -> FastAPI:
    app = FastAPI()
    app.include_router(me_router, prefix="/api")

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


def _prepare_users_table(db_path: Path) -> None:
    import asyncio

    async def _init() -> None:
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute(USERS_TABLE_SQL)
            await db.commit()

    asyncio.run(_init())


def test_me_dev_mode_without_telegram_auth_returns_user(tmp_path: Path) -> None:
    db_path = tmp_path / "dev_auth.sqlite3"
    _prepare_users_table(db_path)

    old_env = settings.env
    old_dev_enabled = settings.dev_auth_enabled
    old_dev_user_id = settings.dev_auth_user_id
    object.__setattr__(settings, "env", "dev")
    object.__setattr__(settings, "dev_auth_enabled", True)
    object.__setattr__(settings, "dev_auth_user_id", 1)

    app = _build_app(db_path)
    try:
        with TestClient(app) as client:
            resp = client.get("/api/me")
            assert resp.status_code == 200
            body = resp.json()
            assert body["id"] == 1
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)


def test_me_prod_mode_without_telegram_auth_is_unauthorized(tmp_path: Path) -> None:
    db_path = tmp_path / "prod_auth.sqlite3"
    _prepare_users_table(db_path)

    old_env = settings.env
    old_dev_enabled = settings.dev_auth_enabled
    old_dev_user_id = settings.dev_auth_user_id
    object.__setattr__(settings, "env", "prod")
    object.__setattr__(settings, "dev_auth_enabled", False)
    object.__setattr__(settings, "dev_auth_user_id", 1)

    app = _build_app(db_path)
    try:
        with TestClient(app) as client:
            resp = client.get("/api/me")
            assert resp.status_code == 401
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)
