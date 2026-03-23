from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.deps import get_current_user
from backend.app.api.routes import events as events_route
from backend.app.db import get_db
from backend.app.settings import settings


async def _dummy_db() -> AsyncGenerator[object, None]:
    class DummyDB:
        async def commit(self) -> None:
            return

    yield DummyDB()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(events_route.router, prefix="/api")
    app.dependency_overrides[get_db] = _dummy_db
    return app


def test_permissions_without_auth() -> None:
    old_env = settings.env
    old_dev_auth = settings.dev_auth_enabled
    object.__setattr__(settings, "env", "prod")
    object.__setattr__(settings, "dev_auth_enabled", False)
    app = _build_app()
    try:
        with TestClient(app) as client:
            resp = client.get("/api/events/permissions")
            assert resp.status_code == 200
            body = resp.json()
            assert body["can_create_member_event"] is False
            assert "Войдите" in body["reason"]
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_auth)


def test_member_event_with_auth_user(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: {"id": 42, "role": "member", "is_admin": 0}

    async def _fake_create_member_event(db, *, payload, current_user):
        return {
            "id": 999,
            "title": payload["title"],
            "event_id": 999,
            "is_club_event": False,
            "created_by_user_id": int(current_user["id"]),
            "created_by_role": "member",
            "registered": 1,
            "capacity": int(payload["capacity"]),
        }

    monkeypatch.setattr(events_route.events_service, "create_member_event", _fake_create_member_event)

    with TestClient(app) as client:
        resp = client.post(
            "/api/events/member",
            json={
                "title": "Test member event",
                "description": "desc",
                "starts_at": "2099-03-10T19:00:00",
                "event_type": "online",
                "capacity": 6,
                "category": "Нетворкинг",
                "tags": ["Нетворкинг"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["event"]["created_by_role"] == "member"
        assert body["event"]["created_by_user_id"] == 42


def test_club_event_for_member_forbidden() -> None:
    app = _build_app()
    app.dependency_overrides[get_current_user] = lambda: {"id": 42, "role": "member", "is_admin": 0}

    with TestClient(app) as client:
        resp = client.post(
            "/api/events/club",
            json={
                "title": "Club event",
                "description": "desc",
                "starts_at": "2099-03-10T19:00:00",
                "event_type": "online",
                "capacity": 6,
            },
        )
        assert resp.status_code == 403
