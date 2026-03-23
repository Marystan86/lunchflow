from datetime import datetime

import aiosqlite


async def create_event(
    db: aiosqlite.Connection,
    *,
    owner_id: int,
    title: str,
    description: str | None,
    category: str | None,
    city: str | None,
    location: str | None,
    tags: str | None,
    event_type: str,
    capacity: int,
    starts_at: str,
    created_by_user_id: int,
    created_by_role: str,
    created_source: str = "app",
    club_label: str | None = None,
    is_club_event: bool = False,
    status: str = "published",
) -> dict:
    created_at = datetime.utcnow().isoformat()
    cursor = await db.execute(
        """
        INSERT INTO events (
            owner_id, created_by_user_id, created_by_role, created_source, club_label, is_club_event,
            title, description, category, city, location, tags, event_type, capacity, starts_at, status, created_at, confirmed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            int(owner_id),
            int(created_by_user_id),
            created_by_role,
            created_source,
            club_label,
            1 if is_club_event else 0,
            title,
            description,
            category,
            city,
            location,
            tags,
            event_type,
            int(capacity),
            starts_at,
            status,
            created_at,
        ),
    )
    return await get_event_by_id(db, int(cursor.lastrowid))


async def get_event_by_id(db: aiosqlite.Connection, event_id: int) -> dict | None:
    cursor = await db.execute(
        """
        SELECT e.*, u.full_name AS created_by_name
        FROM events e
        LEFT JOIN users u ON u.id = e.created_by_user_id
        WHERE e.id = ? LIMIT 1
        """,
        (int(event_id),),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_events(db: aiosqlite.Connection, *, is_club_event: bool | None, limit: int = 50) -> list[dict]:
    if is_club_event is None:
        where_sql = "WHERE datetime(e.starts_at) >= datetime('now')"
        params = (int(limit),)
    else:
        where_sql = "WHERE is_club_event = ? AND datetime(e.starts_at) >= datetime('now')"
        params = (1 if is_club_event else 0, int(limit))
    cursor = await db.execute(
        f"""
        SELECT
               e.*,
               u.full_name AS created_by_name,
               (
                  SELECT COUNT(*)
                  FROM event_participants ep
                  WHERE ep.event_id = e.id AND ep.status IN ('registered', 'attended', 'joined')
               ) AS registered_count
        FROM events e
        LEFT JOIN users u ON u.id = e.created_by_user_id
        {where_sql}
        ORDER BY datetime(e.starts_at) ASC, e.id ASC
        LIMIT ?
        """,
        params,
    )
    return [dict(row) for row in await cursor.fetchall()]


async def set_participant_status(
    db: aiosqlite.Connection,
    *,
    event_id: int,
    user_id: int,
    status: str,
) -> None:
    cursor = await db.execute(
        """
        SELECT status
        FROM event_participants
        WHERE event_id = ? AND user_id = ?
        LIMIT 1
        """,
        (int(event_id), int(user_id)),
    )
    existing = await cursor.fetchone()
    if existing is None:
        await db.execute(
            """
            INSERT INTO event_participants (event_id, user_id, status, joined_at)
            VALUES (?, ?, ?, ?)
            """,
            (int(event_id), int(user_id), status, datetime.utcnow().isoformat()),
        )
        return
    await db.execute(
        "UPDATE event_participants SET status = ? WHERE event_id = ? AND user_id = ?",
        (status, int(event_id), int(user_id)),
    )


async def count_registered(db: aiosqlite.Connection, event_id: int) -> int:
    cursor = await db.execute(
        """
        SELECT COUNT(*)
        FROM event_participants
        WHERE event_id = ? AND status IN ('registered', 'attended', 'joined')
        """,
        (int(event_id),),
    )
    row = await cursor.fetchone()
    return int(row[0] if row else 0)
