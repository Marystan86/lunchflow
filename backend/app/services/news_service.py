import json

import aiosqlite
from fastapi import HTTPException

from backend.app.models.schemas import NewsCreateRequest
from backend.app.repositories import news_repo


def _default_tag(news_type: str | None) -> str:
    mapping = {
        "admin_post": "Клуб",
        "event_announcement": "Ивент",
        "event_summary": "Итоги",
    }
    return mapping.get((news_type or "").strip().lower(), "Клуб")


def _parse_media_urls(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def _to_public(row: dict) -> dict:
    news_type = row.get("type")
    return {
        "id": int(row["id"]),
        "type": news_type,
        "tag": (row.get("tag") or "").strip() or _default_tag(news_type),
        "title": row["title"],
        "body": row["body"],
        "media_urls": _parse_media_urls(row.get("media_urls")),
        "entity_type": row.get("entity_type"),
        "entity_id": row.get("entity_id"),
        "created_by_user_id": row.get("created_by_user_id"),
        "created_at": row["created_at"],
        "is_pinned": bool(row.get("is_pinned", 0)),
    }


async def list_feed(db: aiosqlite.Connection, user: dict, limit: int, offset: int) -> list[dict]:
    if (user.get("status") or "").lower() != "active":
        raise HTTPException(status_code=403, detail="only active members can view news feed")
    rows = await news_repo.list_news(db, limit=limit, offset=offset, include_inactive=False)
    return [_to_public(row) for row in rows]


async def list_public_feed(db: aiosqlite.Connection, limit: int, offset: int) -> list[dict]:
    rows = await news_repo.list_news(db, limit=limit, offset=offset, include_inactive=False)
    return [_to_public(row) for row in rows]


async def create_admin_post(db: aiosqlite.Connection, admin_user: dict, payload: NewsCreateRequest) -> dict:
    media_urls_json = None
    if payload.media_urls is not None:
        media_urls_json = json.dumps(payload.media_urls, ensure_ascii=False)
    row = await news_repo.create_news(
        db,
        type="admin_post",
        tag=(payload.tag or "").strip() or _default_tag("admin_post"),
        created_at=payload.created_at,
        title=payload.title.strip(),
        body=payload.body.strip(),
        media_urls_json=media_urls_json,
        created_by_user_id=int(admin_user["id"]),
        is_pinned=1 if payload.is_pinned else 0,
    )
    await db.commit()
    if row is None:
        raise HTTPException(status_code=500, detail="failed to create news")
    return _to_public(row)


async def create_event_announcement(
    db: aiosqlite.Connection,
    event_id: int,
    title: str,
    body: str,
    tag: str | None = None,
    created_at: str | None = None,
    media_urls: list[str] | None = None,
) -> dict:
    row = await news_repo.create_news(
        db,
        type="event_announcement",
        tag=(tag or "").strip() or _default_tag("event_announcement"),
        created_at=created_at,
        title=title.strip(),
        body=body.strip(),
        media_urls_json=json.dumps(media_urls or [], ensure_ascii=False),
        entity_type="event",
        entity_id=int(event_id),
        created_by_user_id=None,
        is_pinned=0,
    )
    await db.commit()
    if row is None:
        raise HTTPException(status_code=500, detail="failed to create event announcement")
    return _to_public(row)


async def create_event_summary(
    db: aiosqlite.Connection,
    event_id: int,
    title: str,
    body: str,
    tag: str | None = None,
    created_at: str | None = None,
    media_urls: list[str] | None = None,
) -> dict:
    row = await news_repo.create_news(
        db,
        type="event_summary",
        tag=(tag or "").strip() or _default_tag("event_summary"),
        created_at=created_at,
        title=title.strip(),
        body=body.strip(),
        media_urls_json=json.dumps(media_urls or [], ensure_ascii=False),
        entity_type="event",
        entity_id=int(event_id),
        created_by_user_id=None,
        is_pinned=0,
    )
    await db.commit()
    if row is None:
        raise HTTPException(status_code=500, detail="failed to create event summary")
    return _to_public(row)


async def create_event_news(db: aiosqlite.Connection, event: dict) -> dict:
    event_id = int(event["id"])
    event_title = (event.get("title") or "").strip() or "Событие"
    event_body = (event.get("description") or "").strip() or "Опубликована новая групповая встреча."
    row = await news_repo.create_news(
        db,
        type="event_announcement",
        tag="announcement",
        title=f"Новая встреча: {event_title}",
        body=event_body,
        media_urls_json=json.dumps([], ensure_ascii=False),
        entity_type="event",
        entity_id=event_id,
        created_by_user_id=None,
        is_pinned=0,
    )
    await db.commit()
    if row is None:
        raise HTTPException(status_code=500, detail="failed to create event news")
    return _to_public(row)


async def pin_news(db: aiosqlite.Connection, news_id: int, is_pinned: bool) -> dict:
    row = await news_repo.set_news_pinned(db, int(news_id), 1 if is_pinned else 0)
    await db.commit()
    if row is None:
        raise HTTPException(status_code=404, detail="news not found")
    return _to_public(row)


async def deactivate_news(db: aiosqlite.Connection, news_id: int) -> dict:
    row = await news_repo.set_news_active(db, int(news_id), 0)
    await db.commit()
    if row is None:
        raise HTTPException(status_code=404, detail="news not found")
    return _to_public(row)
