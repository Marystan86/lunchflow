from datetime import datetime, timedelta

import aiosqlite


def _ph(values: list[int]) -> str:
    return ",".join(["?"] * len(values))


async def list_sample_users(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute("SELECT * FROM users WHERE source = 'sample' ORDER BY id")
    return [dict(row) for row in await cursor.fetchall()]


async def list_sample_user_ids(db: aiosqlite.Connection) -> list[int]:
    cursor = await db.execute("SELECT id FROM users WHERE source = 'sample' ORDER BY id")
    return [int(row[0]) for row in await cursor.fetchall()]


async def list_meetings_for_user(db: aiosqlite.Connection, user_id: int) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT id, initiator_id, receiver_id, status, created_at, confirmed_at
        FROM meetings
        WHERE LOWER(status) = 'confirmed' AND (initiator_id = ? OR receiver_id = ?)
        ORDER BY id
        """,
        (int(user_id), int(user_id)),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def cleanup_sample_data(db: aiosqlite.Connection) -> dict:
    user_ids = await list_sample_user_ids(db)
    if not user_ids:
        await db.commit()
        return {
            "users_deleted": 0,
            "meetings_deleted": 0,
            "events_deleted": 0,
            "points_deleted": 0,
            "votes_deleted": 0,
            "user_badges_deleted": 0,
            "news_deleted": 0,
            "participants_deleted": 0,
        }

    uid_ph = _ph(user_ids)

    cur = await db.execute(
        f"SELECT id FROM meetings WHERE initiator_id IN ({uid_ph}) OR receiver_id IN ({uid_ph})",
        tuple(user_ids + user_ids),
    )
    meeting_ids = [int(r[0]) for r in await cur.fetchall()]

    cur = await db.execute(
        f"SELECT id FROM events WHERE owner_id IN ({uid_ph}) OR created_source = 'seed'",
        tuple(user_ids),
    )
    event_ids = [int(r[0]) for r in await cur.fetchall()]

    votes_deleted = 0
    if meeting_ids:
        mid_ph = _ph(meeting_ids)
        cur = await db.execute(
            f"""
            DELETE FROM badge_votes
            WHERE from_user_id IN ({uid_ph})
               OR to_user_id IN ({uid_ph})
               OR meeting_id IN ({mid_ph})
            """,
            tuple(user_ids + user_ids + meeting_ids),
        )
        votes_deleted = cur.rowcount or 0
    else:
        cur = await db.execute(
            f"DELETE FROM badge_votes WHERE from_user_id IN ({uid_ph}) OR to_user_id IN ({uid_ph})",
            tuple(user_ids + user_ids),
        )
        votes_deleted = cur.rowcount or 0

    cur = await db.execute(f"DELETE FROM user_badges WHERE user_id IN ({uid_ph})", tuple(user_ids))
    user_badges_deleted = cur.rowcount or 0

    cur = await db.execute(f"DELETE FROM points_ledger WHERE user_id IN ({uid_ph})", tuple(user_ids))
    points_deleted = cur.rowcount or 0

    participants_deleted = 0
    if event_ids:
        eid_ph = _ph(event_ids)
        cur = await db.execute(
            f"DELETE FROM event_participants WHERE user_id IN ({uid_ph}) OR event_id IN ({eid_ph})",
            tuple(user_ids + event_ids),
        )
        participants_deleted = cur.rowcount or 0
    else:
        cur = await db.execute(f"DELETE FROM event_participants WHERE user_id IN ({uid_ph})", tuple(user_ids))
        participants_deleted = cur.rowcount or 0

    news_deleted = 0
    if event_ids:
        eid_ph = _ph(event_ids)
        cur = await db.execute(
            f"""
            DELETE FROM news
            WHERE created_by_user_id IN ({uid_ph})
               OR (entity_type = 'event' AND entity_id IN ({eid_ph}))
            """,
            tuple(user_ids + event_ids),
        )
        news_deleted = cur.rowcount or 0
    else:
        cur = await db.execute(
            f"DELETE FROM news WHERE created_by_user_id IN ({uid_ph})",
            tuple(user_ids),
        )
        news_deleted = cur.rowcount or 0

    meetings_deleted = 0
    if meeting_ids:
        mid_ph = _ph(meeting_ids)
        cur = await db.execute(f"DELETE FROM meetings WHERE id IN ({mid_ph})", tuple(meeting_ids))
        meetings_deleted = cur.rowcount or 0

    events_deleted = 0
    if event_ids:
        eid_ph = _ph(event_ids)
        cur = await db.execute(f"DELETE FROM events WHERE id IN ({eid_ph})", tuple(event_ids))
        events_deleted = cur.rowcount or 0

    cur = await db.execute(f"DELETE FROM users WHERE id IN ({uid_ph})", tuple(user_ids))
    users_deleted = cur.rowcount or 0

    await db.commit()
    return {
        "users_deleted": int(users_deleted),
        "meetings_deleted": int(meetings_deleted),
        "events_deleted": int(events_deleted),
        "points_deleted": int(points_deleted),
        "votes_deleted": int(votes_deleted),
        "user_badges_deleted": int(user_badges_deleted),
        "news_deleted": int(news_deleted),
        "participants_deleted": int(participants_deleted),
    }


async def create_sample_user(
    db: aiosqlite.Connection,
    *,
    tg_id: int,
    full_name: str,
    tg_username: str,
    role: str,
    source: str,
    status: str,
    company_name: str,
    industry: str,
    annual_revenue: str,
    employee_count: int,
    core_competencies: str,
    goal_2025: str,
    club_request: str,
    hobbies: str,
    help_offer: str,
) -> int:
    cursor = await db.execute(
        """
        INSERT INTO users (
            tg_id, source, tg_username, full_name, photo_url, role, is_admin, status,
            company_name, industry, annual_revenue, employee_count, core_competencies,
            goal_2025, club_request, hobbies, help_offer, created_at, updated_at
        ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            int(tg_id),
            source,
            tg_username,
            full_name,
            role,
            1 if role in {"admin", "superadmin", "community_admin"} else 0,
            status,
            company_name,
            industry,
            annual_revenue,
            int(employee_count),
            core_competencies,
            goal_2025,
            club_request,
            hobbies,
            help_offer,
        ),
    )
    return int(cursor.lastrowid)


async def ensure_community_admin_user(db: aiosqlite.Connection) -> int:
    cur = await db.execute(
        """
        SELECT id
        FROM users
        WHERE role IN ('community_admin', 'superadmin', 'admin')
           OR is_admin = 1
        ORDER BY id
        LIMIT 1
        """
    )
    row = await cur.fetchone()
    if row:
        return int(row[0])

    tg_id = 999000999
    cur = await db.execute("SELECT id FROM users WHERE tg_id = ? LIMIT 1", (tg_id,))
    row = await cur.fetchone()
    if row:
        user_id = int(row[0])
        await db.execute(
            """
            UPDATE users
            SET role = 'community_admin', is_admin = 1, status = 'active', source = COALESCE(source, 'real'),
                full_name = COALESCE(full_name, 'Комьюнити-админ'),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (user_id,),
        )
        return user_id

    cur = await db.execute(
        """
        INSERT INTO users (
            tg_id, source, tg_username, full_name, role, is_admin, status, created_at, updated_at
        ) VALUES (?, 'real', 'community_admin_999', 'Комьюнити-админ', 'community_admin', 1, 'active', datetime('now'), datetime('now'))
        """,
        (tg_id,),
    )
    return int(cur.lastrowid)


async def create_confirmed_meeting(
    db: aiosqlite.Connection,
    *,
    initiator_id: int,
    receiver_id: int,
    created_at: str,
) -> int:
    confirmed_at = (datetime.fromisoformat(created_at) + timedelta(hours=2)).isoformat()
    cursor = await db.execute(
        """
        INSERT INTO meetings (initiator_id, receiver_id, status, created_at, confirmed_at)
        VALUES (?, ?, 'confirmed', ?, ?)
        """,
        (int(initiator_id), int(receiver_id), created_at, confirmed_at),
    )
    return int(cursor.lastrowid)


async def create_event(
    db: aiosqlite.Connection,
    *,
    owner_id: int,
    created_by_user_id: int,
    created_by_role: str,
    created_source: str,
    club_label: str | None,
    is_club_event: int,
    title: str,
    description: str,
    category: str | None,
    event_type: str,
    capacity: int,
    starts_at: str,
    status: str,
) -> int:
    confirmed_at = datetime.utcnow().isoformat() if status == "confirmed" else None
    cursor = await db.execute(
        """
        INSERT INTO events (
            owner_id, created_by_user_id, created_by_role, created_source, club_label, is_club_event,
            title, description, category, event_type, capacity, starts_at, status, created_at, confirmed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            event_type,
            int(capacity),
            starts_at,
            status,
            datetime.utcnow().isoformat(),
            confirmed_at,
        ),
    )
    return int(cursor.lastrowid)


async def add_event_participant(
    db: aiosqlite.Connection,
    *,
    event_id: int,
    user_id: int,
    status: str,
    joined_at: str,
) -> None:
    await db.execute(
        """
        INSERT OR REPLACE INTO event_participants (event_id, user_id, status, joined_at)
        VALUES (?, ?, ?, ?)
        """,
        (int(event_id), int(user_id), status, joined_at),
    )


async def count_table(db: aiosqlite.Connection, table_name: str) -> int:
    cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
    row = await cursor.fetchone()
    return int(row[0] if row and row[0] is not None else 0)
