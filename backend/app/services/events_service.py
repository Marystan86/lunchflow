import json
from datetime import datetime, timezone

import aiosqlite
from fastapi import HTTPException

from backend.app.repositories import events_repo, users_repo
from backend.app.services import news_service
from backend.app.settings import settings


async def on_event_published(
    db: aiosqlite.Connection,
    *,
    event_id: int,
    title: str,
    summary: str,
    tag: str | None = None,
    media_urls: list[str] | None = None,
) -> dict:
    """Hook point: call this when event is published."""
    return await news_service.create_event_announcement(
        db=db,
        event_id=event_id,
        title=title,
        body=summary,
        tag=tag,
        media_urls=media_urls,
    )


async def on_event_finished(
    db: aiosqlite.Connection,
    *,
    event_id: int,
    title: str,
    summary: str,
    tag: str | None = None,
    media_urls: list[str] | None = None,
) -> dict:
    """Hook point: call this when event is confirmed/finished."""
    return await news_service.create_event_summary(
        db=db,
        event_id=event_id,
        title=title,
        body=summary,
        tag=tag,
        media_urls=media_urls,
    )


def _parse_starts_at(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="starts_at is required")

    # JS toISOString() returns trailing Z; normalize for fromisoformat
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="starts_at must be ISO datetime") from exc

    if dt.tzinfo is None:
        # Treat naive datetime as UTC for consistent comparison/storage.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_creator_id(current_user: dict) -> int:
    creator_raw = current_user.get("id") if isinstance(current_user, dict) else None
    if creator_raw not in (None, "", 0, "0"):
        return int(creator_raw)

    if settings.env == "dev" and settings.dev_auth_enabled:
        return int(settings.dev_auth_user_id)

    raise HTTPException(status_code=403, detail="creator_id is required")


async def create_member_event(db: aiosqlite.Connection, *, payload: dict, current_user: dict) -> dict:
    required_fields = ["title", "description", "starts_at", "event_type", "capacity"]
    for field in required_fields:
        if payload.get(field) in (None, "", []):
            raise HTTPException(status_code=400, detail=f"{field} is required")

    creator_id = _resolve_creator_id(current_user)
    creator = await users_repo.get_by_id(db, creator_id)
    if creator is None:
        raise HTTPException(status_code=403, detail="user not found")
    if creator.get("role") in {"admin", "superadmin", "community_admin"} or int(creator.get("is_admin") or 0) == 1:
        raise HTTPException(status_code=400, detail="admin should create club events")

    starts_at_dt = _parse_starts_at(str(payload["starts_at"]))
    if starts_at_dt < datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="starts_at cannot be in the past")

    capacity = int(payload.get("capacity") or 0)
    if capacity < 2:
        raise HTTPException(status_code=409, detail="capacity must be >= 2")

    fmt = str(payload.get("event_type") or "").strip().lower()
    if fmt not in {"online", "offline"}:
        raise HTTPException(status_code=400, detail="event_type must be online or offline")

    city = (payload.get("city") or "").strip() or None
    location = (payload.get("location") or "").strip() or None
    if fmt == "offline" and not city:
        raise HTTPException(status_code=400, detail="city is required for offline events")
    if fmt == "online":
        city = None
        location = None

    tags = payload.get("tags") or []
    if tags is not None and not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="tags must be array")
    tags = [str(t).strip() for t in tags if str(t).strip()][:10]

    event_id = await events_repo.create_event(
        db,
        owner_id=creator_id,
        created_by_user_id=creator_id,
        created_by_role="member",
        created_source="app",
        club_label=None,
        is_club_event=0,
        title=str(payload["title"]).strip(),
        description=str(payload["description"]).strip(),
        category=payload.get("category"),
        city=city,
        location=location,
        tags=tags,
        event_type=fmt,
        capacity=capacity,
        starts_at=starts_at_dt.isoformat(),
        status="published",
    )

    # Auto-register creator (idempotent). In current schema organizer role is implied by owner_id/creator.
    await events_repo.register_user(db, event_id=int(event_id), user_id=creator_id)
    registered_count = await events_repo.count_registered(db, int(event_id))
    if registered_count > capacity:
        raise HTTPException(status_code=409, detail="capacity exceeded")

    event = await events_repo.get_event_by_id(db, int(event_id))
    if event is None:
        raise HTTPException(status_code=500, detail="event creation failed")

    await news_service.create_event_news(db, event)

    return {
        "id": int(event["id"]),
        "title": event.get("title") or "",
        "subtitle": f"От участника: {event.get('created_by_name')}" if event.get("created_by_name") else "От участника",
        "status": event.get("status") or "published",
        "scheduled_for": event.get("starts_at"),
        "format": event.get("event_type"),
        "city": event.get("city"),
        "location": event.get("location"),
        "message": event.get("description"),
        "event_id": int(event["id"]),
        "is_club_event": bool(event.get("is_club_event", 0)),
        "registered": int(event.get("registered_count") or 0),
        "capacity": int(event.get("capacity") or 0),
        "category": event.get("category"),
        "created_by_user_id": int(event.get("created_by_user_id") or creator_id),
        "created_by_role": event.get("created_by_role"),
        "created_by_name": event.get("created_by_name"),
        "tags": json.loads(event.get("tags") or "[]"),
    }
