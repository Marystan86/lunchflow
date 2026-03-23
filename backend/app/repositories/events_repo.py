from datetime import datetime
import json

import aiosqlite


_event_participants_has_role_column: bool | None = None


async def _has_event_participant_role_column(db: aiosqlite.Connection) -> bool:
    global _event_participants_has_role_column
    if _event_participants_has_role_column is not None:
        return _event_participants_has_role_column
    cur = await db.execute("PRAGMA table_info(event_participants)")
    rows = await cur.fetchall()
    _event_participants_has_role_column = any(str(row[1]) == "role" for row in rows)
    return _event_participants_has_role_column


async def create_event(
    db: aiosqlite.Connection,
    *,
    owner_id: int,
    created_by_user_id: int,
    created_by_role: str,
    created_source: str = "app",
    club_label: str | None = None,
    is_club_event: int = 0,
    title: str,
    description: str | None,
    category: str | None,
    city: str | None,
    location: str | None,
    tags: list[str] | None,
    event_type: str,
    capacity: int,
    starts_at: str,
    status: str = "draft",
    created_at: str | None = None,
    confirmed_at: str | None = None,
) -> int:
    created_at_value = created_at or datetime.utcnow().isoformat()
    cursor = await db.execute(
        """
        INSERT INTO events (
            owner_id, created_by_user_id, created_by_role, created_source, club_label, is_club_event,
            title, description, category, city, location, tags, event_type, capacity, starts_at, status, created_at, confirmed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(owner_id),
            int(created_by_user_id),
            created_by_role,
            created_source,
            club_label,
            int(is_club_event),
            title,
            description,
            category,
            city,
            location,
            json.dumps(tags or [], ensure_ascii=False),
            event_type,
            int(capacity),
            starts_at,
            status,
            created_at_value,
            confirmed_at,
        ),
    )
    return int(cursor.lastrowid)


async def get_event_by_id(db: aiosqlite.Connection, event_id: int) -> dict | None:
    cur = await db.execute(
        """
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
        WHERE e.id = ?
        LIMIT 1
        """,
        (int(event_id),),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def list_upcoming_events(db: aiosqlite.Connection, *, limit: int = 50) -> list[dict]:
    cur = await db.execute(
        """
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
        WHERE e.status IN ('published', 'confirmed')
          AND datetime(e.starts_at) >= datetime('now')
        ORDER BY datetime(e.starts_at) ASC, e.id ASC
        LIMIT ?
        """,
        (int(limit),),
    )
    return [dict(r) for r in await cur.fetchall()]


async def count_registered(db: aiosqlite.Connection, event_id: int) -> int:
    cur = await db.execute(
        """
        SELECT COUNT(*)
        FROM event_participants
        WHERE event_id = ? AND status IN ('registered', 'attended', 'joined')
        """,
        (int(event_id),),
    )
    row = await cur.fetchone()
    return int(row[0] if row else 0)


async def register_user(db: aiosqlite.Connection, event_id: int, user_id: int) -> None:
    has_role_column = await _has_event_participant_role_column(db)
    cur = await db.execute(
        """
        SELECT status
        FROM event_participants
        WHERE event_id = ? AND user_id = ?
        LIMIT 1
        """,
        (int(event_id), int(user_id)),
    )
    row = await cur.fetchone()
    if row is None:
        if has_role_column:
            await db.execute(
                """
                INSERT INTO event_participants (event_id, user_id, status, joined_at, role)
                VALUES (?, ?, 'registered', ?, 'organizer')
                """,
                (int(event_id), int(user_id), datetime.utcnow().isoformat()),
            )
        else:
            await db.execute(
                """
                INSERT INTO event_participants (event_id, user_id, status, joined_at)
                VALUES (?, ?, 'registered', ?)
                """,
                (int(event_id), int(user_id), datetime.utcnow().isoformat()),
            )
        return
    if has_role_column:
        await db.execute(
            """
            UPDATE event_participants
            SET status = 'registered', role = COALESCE(role, 'organizer')
            WHERE event_id = ? AND user_id = ?
            """,
            (int(event_id), int(user_id)),
        )
    else:
        await db.execute(
            """
            UPDATE event_participants
            SET status = 'registered'
            WHERE event_id = ? AND user_id = ?
            """,
            (int(event_id), int(user_id)),
        )
