from collections.abc import AsyncGenerator
from pathlib import Path

import aiosqlite
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.dev import router as dev_router
from backend.app.db import USERS_TABLE_SQL, get_db
from backend.app.settings import settings


def _build_app(db_path: Path) -> FastAPI:
    app = FastAPI()
    app.include_router(dev_router, prefix="/api")

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


def test_dev_users_endpoint_returns_catalog_in_dev(tmp_path: Path) -> None:
    db_path = tmp_path / "dev_users.sqlite3"
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
            resp = client.get("/api/dev/users")
            assert resp.status_code == 200
            body = resp.json()
            assert isinstance(body, list)
            assert len(body) >= 5
            assert body[0]["id"] == 1
            assert body[0]["name"] == "Maydan"
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)


def test_dev_users_endpoint_is_not_available_in_prod(tmp_path: Path) -> None:
    db_path = tmp_path / "prod_users.sqlite3"
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
            resp = client.get("/api/dev/users")
            assert resp.status_code == 404
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)


def test_dev_whoami_respects_x_dev_user_id_header(tmp_path: Path) -> None:
    db_path = tmp_path / "dev_whoami.sqlite3"
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
            resp = client.get("/api/dev/whoami", headers={"X-Dev-User-Id": "4"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["id"] == 4
            assert body["name"] == "Vera Akhmetova"
            assert body["env"] == "dev"
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)
