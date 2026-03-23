from datetime import datetime

import aiosqlite


async def create_news(
    db: aiosqlite.Connection,
    *,
    type: str,
    tag: str | None = None,
    created_at: str | None = None,
    title: str,
    body: str,
    media_urls_json: str | None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    created_by_user_id: int | None = None,
    is_pinned: int = 0,
) -> dict | None:
    created_at_value = created_at or datetime.utcnow().isoformat()
    cursor = await db.execute(
        """
        INSERT INTO news (
            type, tag, title, body, media_urls, entity_type, entity_id, created_by_user_id,
            created_at, is_pinned, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            type,
            tag,
            title,
            body,
            media_urls_json,
            entity_type,
            entity_id,
            created_by_user_id,
            created_at_value,
            int(is_pinned),
        ),
    )
    news_id = int(cursor.lastrowid)
    return await get_news_by_id(db, news_id)


async def list_news(
    db: aiosqlite.Connection,
    *,
    limit: int = 50,
    offset: int = 0,
    include_inactive: bool = False,
) -> list[dict]:
    where_sql = "" if include_inactive else "WHERE is_active = 1"
    cursor = await db.execute(
        f"""
        SELECT *
        FROM news
        {where_sql}
        ORDER BY is_pinned DESC, created_at DESC
        LIMIT ? OFFSET ?
        """,
        (int(limit), int(offset)),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_news_by_id(db: aiosqlite.Connection, news_id: int) -> dict | None:
    cursor = await db.execute("SELECT * FROM news WHERE id = ? LIMIT 1", (int(news_id),))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def set_news_active(db: aiosqlite.Connection, news_id: int, is_active: int) -> dict | None:
    await db.execute("UPDATE news SET is_active = ? WHERE id = ?", (int(is_active), int(news_id)))
    return await get_news_by_id(db, news_id)


async def set_news_pinned(db: aiosqlite.Connection, news_id: int, is_pinned: int) -> dict | None:
    await db.execute("UPDATE news SET is_pinned = ? WHERE id = ?", (int(is_pinned), int(news_id)))
    return await get_news_by_id(db, news_id)
