import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException

from backend.app.db import get_db
from backend.app.repositories import users_repo
from backend.app.security.telegram_auth import verify_telegram_init_data
from backend.app.settings import is_admin, settings


def _json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _as_user_public(user: dict) -> dict:
    return {
        "id": int(user["id"]),
        "tg_id": int(user["tg_id"]),
        "full_name": user.get("full_name") or "",
        "tg_username": user.get("tg_username"),
        "photo_url": user.get("photo_url"),
        "role": user.get("role") or "member",
        "status": user.get("status") or "pending",
    }


def _as_member_item(user: dict) -> dict:
    item = _as_user_public(user)
    item.update(
        {
            "city": user.get("city"),
            "company": user.get("company"),
            "position": user.get("position"),
            "company_name": user.get("company_name"),
            "industry": user.get("industry"),
            "annual_revenue": user.get("annual_revenue"),
            "employee_count": user.get("employee_count"),
            "core_competencies": user.get("core_competencies"),
            "goal_2025": user.get("goal_2025"),
            "club_request": user.get("club_request"),
            "hobbies": user.get("hobbies"),
            "help_offer": user.get("help_offer"),
            "badges_preview": user.get("badges_preview") or [],
            "help_tags": _json_load(user.get("help_tags"), []),
            "need_tags": _json_load(user.get("need_tags"), []),
        }
    )
    return item


def _token_secret() -> bytes:
    seed = settings.bot_token or "dev-insecure-token"
    return hashlib.sha256(f"{seed}:meet-eat-api".encode("utf-8")).digest()


def create_access_token(user_id: int, ttl_seconds: int = 60 * 60 * 24 * 14) -> str:
    payload = {
        "uid": int(user_id),
        "exp": int(time.time()) + int(ttl_seconds),
    }
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    signature = hmac.new(_token_secret(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def decode_access_token(token: str) -> int:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    expected = hmac.new(_token_secret(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="invalid token")

    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="token expired")

    uid = payload.get("uid")
    if uid is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return int(uid)


async def auth_with_telegram(init_data: str) -> tuple[dict, str]:
    if not settings.bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN is not configured")

    tg_user = verify_telegram_init_data(init_data, settings.bot_token)
    full_name = " ".join(part for part in [tg_user.get("first_name"), tg_user.get("last_name")] if part).strip()

    async for db in get_db():
        user = await users_repo.get_by_tg_id(db, int(tg_user["id"]))
        role = "admin" if is_admin(int(tg_user["id"])) else "member"

        if user is None:
            user = await users_repo.create_user_from_tg(db, tg_user, role=role, status="active")
        else:
            patch: dict[str, Any] = {
                "tg_username": tg_user.get("username"),
                "full_name": full_name or user.get("full_name") or "",
                "photo_url": tg_user.get("photo_url"),
            }
            if role in {"admin", "superadmin"} and user.get("role") not in {"admin", "superadmin"}:
                patch["role"] = "admin"
            user = await users_repo.update_user_profile(db, int(user["id"]), patch)

        token = create_access_token(int(user["id"]))
        return _as_user_public(user), token

    raise HTTPException(status_code=500, detail="database error")


async def get_me(user: dict) -> dict:
    return _as_member_item(user) | {
        "bio": user.get("bio"),
        "contacts": _json_load(user.get("contacts"), {}),
        "visibility": user.get("visibility") or "members_only",
    }


async def update_me(user_id: int, payload: dict) -> dict:
    patch = dict(payload)

    for key in ("help_tags", "need_tags"):
        if key in patch and isinstance(patch[key], list):
            patch[key] = json.dumps([str(tag).strip() for tag in patch[key] if str(tag).strip()], ensure_ascii=False)

    if "contacts" in patch and patch["contacts"] is not None:
        patch["contacts"] = json.dumps(patch["contacts"], ensure_ascii=False)

    async for db in get_db():
        user = await users_repo.update_user_profile(db, int(user_id), patch)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        return _as_member_item(user) | {
            "bio": user.get("bio"),
            "contacts": _json_load(user.get("contacts"), {}),
            "visibility": user.get("visibility") or "members_only",
        }

    raise HTTPException(status_code=500, detail="database error")


async def list_members(filters: dict) -> list[dict]:
    async for db in get_db():
        rows = await users_repo.list_members(
            db,
            query=filters.get("query"),
            city=filters.get("city"),
            tags=filters.get("tags"),
            limit=int(filters.get("limit", 50)),
            offset=int(filters.get("offset", 0)),
        )
        user_ids = [int(row["id"]) for row in rows if row.get("id") is not None]
        badges_by_user = await users_repo.list_badges_preview_for_users(db, user_ids, limit_per_user=3)
        for row in rows:
            row["badges_preview"] = badges_by_user.get(int(row["id"]), [])
        return [_as_member_item(row) for row in rows]

    raise HTTPException(status_code=500, detail="database error")


async def list_public_members(limit: int = 50, offset: int = 0) -> list[dict]:
    async for db in get_db():
        rows = await users_repo.list_public_members(db, limit=int(limit), offset=int(offset))
        user_ids = [int(row["id"]) for row in rows if row.get("id") is not None]
        badges_by_user = await users_repo.list_badges_preview_for_users(db, user_ids, limit_per_user=3)
        for row in rows:
            row["badges_preview"] = badges_by_user.get(int(row["id"]), [])
        return [_as_member_item(row) for row in rows]
    raise HTTPException(status_code=500, detail="database error")


async def get_member_detail(member_id: int, requester_user: dict) -> dict:
    async for db in get_db():
        member = await users_repo.get_by_id(db, int(member_id))
        if member is None:
            raise HTTPException(status_code=404, detail="member not found")

        detail = _as_member_item(member) | {
            "bio": member.get("bio"),
            "contacts": _json_load(member.get("contacts"), {}),
            "visibility": member.get("visibility") or "members_only",
        }

        is_requester_admin = requester_user.get("role") in {"admin", "superadmin"}
        if detail["visibility"] == "hidden" and not is_requester_admin:
            detail["bio"] = None
            detail["contacts"] = {}

        return detail

    raise HTTPException(status_code=500, detail="database error")
