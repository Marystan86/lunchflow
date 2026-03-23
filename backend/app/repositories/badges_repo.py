from collections.abc import Sequence

import aiosqlite


SYSTEM_SEED_BADGES: tuple[dict, ...] = (
    {
        "code": "networker",
        "title": "Networker",
        "description": "Подтверждено 5 встреч",
        "icon": "🤝",
        "badge_type": "system",
        "grant_mode": "auto",
        "criteria_type": "meetings_confirmed_count",
        "criteria_value": 5,
        "vote_threshold": None,
        "cooldown_days": 30,
        "is_active": 1,
    },
    {
        "code": "host",
        "title": "Host",
        "description": "Провел 2 подтвержденных события",
        "icon": "🎤",
        "badge_type": "system",
        "grant_mode": "auto",
        "criteria_type": "events_hosted_confirmed_count",
        "criteria_value": 2,
        "vote_threshold": None,
        "cooldown_days": 30,
        "is_active": 1,
    },
    {
        "code": "explorer",
        "title": "Explorer",
        "description": "Посетил 3 подтвержденных события",
        "icon": "🧭",
        "badge_type": "system",
        "grant_mode": "auto",
        "criteria_type": "events_attended_confirmed_count",
        "criteria_value": 3,
        "vote_threshold": None,
        "cooldown_days": 30,
        "is_active": 1,
    },
)

PEER_SEED_BADGES: tuple[dict, ...] = (
    {
        "code": "pleasant_talker",
        "title": "Приятный собеседник",
        "description": "Коллеги подтвердили приятное общение",
        "icon": "🙂",
        "badge_type": "peer",
        "grant_mode": "vote",
        "criteria_type": None,
        "criteria_value": None,
        "vote_threshold": 3,
        "cooldown_days": 30,
        "is_active": 1,
    },
    {
        "code": "expert",
        "title": "Эксперт",
        "description": "Часто отмечается как эксперт",
        "icon": "🧠",
        "badge_type": "peer",
        "grant_mode": "vote",
        "criteria_type": None,
        "criteria_value": None,
        "vote_threshold": 3,
        "cooldown_days": 30,
        "is_active": 1,
    },
    {
        "code": "helpful",
        "title": "Помог",
        "description": "Помог другим участникам",
        "icon": "🛠️",
        "badge_type": "peer",
        "grant_mode": "vote",
        "criteria_type": None,
        "criteria_value": None,
        "vote_threshold": 3,
        "cooldown_days": 30,
        "is_active": 1,
    },
    {
        "code": "useful_contact",
        "title": "Полезный контакт",
        "description": "Часто получают как полезный контакт",
        "icon": "📇",
        "badge_type": "peer",
        "grant_mode": "vote",
        "criteria_type": None,
        "criteria_value": None,
        "vote_threshold": 3,
        "cooldown_days": 30,
        "is_active": 1,
    },
    {
        "code": "fast_agreement",
        "title": "Быстро договорились",
        "description": "Оперативно согласовывает встречи",
        "icon": "⚡",
        "badge_type": "peer",
        "grant_mode": "vote",
        "criteria_type": None,
        "criteria_value": None,
        "vote_threshold": 3,
        "cooldown_days": 30,
        "is_active": 1,
    },
)


async def _table_exists(db: aiosqlite.Connection, table_name: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    )
    return (await cursor.fetchone()) is not None


async def _table_columns(db: aiosqlite.Connection, table_name: str) -> set[str]:
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in await cursor.fetchall()}


async def upsert_badge(db: aiosqlite.Connection, badge: dict) -> None:
    await db.execute(
        """
        INSERT INTO badges (
            code, title, description, icon, badge_type, grant_mode,
            criteria_type, criteria_value, vote_threshold, cooldown_days, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            icon = excluded.icon,
            badge_type = excluded.badge_type,
            grant_mode = excluded.grant_mode,
            criteria_type = excluded.criteria_type,
            criteria_value = excluded.criteria_value,
            vote_threshold = excluded.vote_threshold,
            cooldown_days = excluded.cooldown_days,
            is_active = excluded.is_active
        """,
        (
            badge["code"],
            badge["title"],
            badge["description"],
            badge["icon"],
            badge["badge_type"],
            badge["grant_mode"],
            badge.get("criteria_type"),
            badge.get("criteria_value"),
            badge.get("vote_threshold"),
            badge.get("cooldown_days", 30),
            badge.get("is_active", 1),
        ),
    )


async def get_badge_by_code(db: aiosqlite.Connection, code: str) -> dict | None:
    cursor = await db.execute("SELECT * FROM badges WHERE code = ? LIMIT 1", (code,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_badges(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT *
        FROM badges
        WHERE is_active = 1
        ORDER BY badge_type ASC, id ASC
        """
    )
    return [dict(row) for row in await cursor.fetchall()]


async def list_user_badges(db: aiosqlite.Connection, user_id: int) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT
            b.*,
            ub.earned_at
        FROM user_badges ub
        JOIN badges b ON b.id = ub.badge_id
        WHERE ub.user_id = ? AND b.is_active = 1
        ORDER BY ub.earned_at DESC, b.id DESC
        """,
        (user_id,),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def user_has_badge(db: aiosqlite.Connection, user_id: int, badge_id: int) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM user_badges WHERE user_id = ? AND badge_id = ? LIMIT 1",
        (user_id, badge_id),
    )
    return (await cursor.fetchone()) is not None


async def insert_vote(
    db: aiosqlite.Connection,
    badge_id: int,
    from_user_id: int,
    to_user_id: int,
    meeting_id: int,
    comment: str | None,
    created_at: str,
) -> bool:
    cursor = await db.execute(
        """
        INSERT OR IGNORE INTO badge_votes (
            badge_id, from_user_id, to_user_id, meeting_id, comment, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (badge_id, from_user_id, to_user_id, meeting_id, comment, created_at),
    )
    return cursor.rowcount > 0


async def count_unique_votes(db: aiosqlite.Connection, badge_id: int, to_user_id: int) -> int:
    cursor = await db.execute(
        """
        SELECT COUNT(DISTINCT from_user_id)
        FROM badge_votes
        WHERE badge_id = ? AND to_user_id = ?
        """,
        (badge_id, to_user_id),
    )
    row = await cursor.fetchone()
    return int(row[0] if row and row[0] is not None else 0)


async def check_cooldown(
    db: aiosqlite.Connection,
    badge_id: int,
    from_user_id: int,
    to_user_id: int,
    cooldown_days: int,
) -> bool:
    cursor = await db.execute(
        """
        SELECT 1
        FROM badge_votes
        WHERE badge_id = ?
          AND from_user_id = ?
          AND to_user_id = ?
          AND (julianday('now') - julianday(replace(substr(created_at, 1, 19), 'T', ' '))) < ?
        LIMIT 1
        """,
        (badge_id, from_user_id, to_user_id, cooldown_days),
    )
    return (await cursor.fetchone()) is not None


async def grant_user_badge(db: aiosqlite.Connection, user_id: int, badge_id: int, earned_at: str) -> bool:
    cursor = await db.execute(
        "INSERT OR IGNORE INTO user_badges (user_id, badge_id, earned_at) VALUES (?, ?, ?)",
        (user_id, badge_id, earned_at),
    )
    return cursor.rowcount > 0


def _build_two_party_clause(
    first_col: str,
    second_col: str,
    user_a: int,
    user_b: int,
) -> tuple[str, Sequence[int]]:
    clause = f"(({first_col} = ? AND {second_col} = ?) OR ({first_col} = ? AND {second_col} = ?))"
    return clause, (user_a, user_b, user_b, user_a)


async def _check_in_meetings(
    db: aiosqlite.Connection,
    meeting_id: int,
    from_user_id: int,
    to_user_id: int,
) -> bool | None:
    if not await _table_exists(db, "meetings"):
        return None

    columns = await _table_columns(db, "meetings")
    if "id" not in columns:
        return None

    status_col = "status" if "status" in columns else None
    pair = None
    for first, second in (
        ("initiator_id", "receiver_id"),
        ("from_user_id", "to_user_id"),
        ("user1_id", "user2_id"),
        ("host_user_id", "guest_user_id"),
        ("initiator_user_id", "responder_user_id"),
    ):
        if first in columns and second in columns:
            pair = (first, second)
            break

    if pair is None:
        return None

    where_parts = ["id = ?"]
    params: list[int | str] = [meeting_id]
    clause, clause_params = _build_two_party_clause(pair[0], pair[1], from_user_id, to_user_id)
    where_parts.append(clause)
    params.extend(clause_params)

    if status_col is not None:
        where_parts.append(f"LOWER({status_col}) IN ('confirmed', 'accepted')")

    query = f"SELECT 1 FROM meetings WHERE {' AND '.join(where_parts)} LIMIT 1"
    cursor = await db.execute(query, tuple(params))
    return (await cursor.fetchone()) is not None


async def _check_in_invites(
    db: aiosqlite.Connection,
    meeting_id: int,
    from_user_id: int,
    to_user_id: int,
) -> bool | None:
    if not await _table_exists(db, "invites"):
        return None

    columns = await _table_columns(db, "invites")
    required = {"id", "from_user_id", "to_user_id", "status"}
    if not required.issubset(columns):
        return None

    clause, clause_params = _build_two_party_clause("from_user_id", "to_user_id", from_user_id, to_user_id)
    cursor = await db.execute(
        f"""
        SELECT 1
        FROM invites
        WHERE id = ?
          AND {clause}
          AND LOWER(status) IN ('confirmed', 'accepted')
        LIMIT 1
        """,
        (meeting_id, *clause_params),
    )
    return (await cursor.fetchone()) is not None


async def is_confirmed_meeting_for_users(
    db: aiosqlite.Connection,
    meeting_id: int,
    from_user_id: int,
    to_user_id: int,
) -> bool:
    from_meetings = await _check_in_meetings(db, meeting_id, from_user_id, to_user_id)
    if from_meetings is not None:
        return from_meetings

    from_invites = await _check_in_invites(db, meeting_id, from_user_id, to_user_id)
    if from_invites is not None:
        return from_invites

    return False


async def get_metric_value(db: aiosqlite.Connection, user_id: int, criteria_type: str | None) -> int:
    if not criteria_type:
        return 0

    if criteria_type == "meetings_confirmed_count":
        if await _table_exists(db, "meetings"):
            columns = await _table_columns(db, "meetings")
            if {"initiator_id", "receiver_id"}.issubset(columns):
                status_filter = " AND LOWER(status) IN ('confirmed', 'accepted')" if "status" in columns else ""
                cursor = await db.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM meetings
                    WHERE (initiator_id = ? OR receiver_id = ?){status_filter}
                    """,
                    (user_id, user_id),
                )
                row = await cursor.fetchone()
                return int(row[0] if row and row[0] is not None else 0)
        if await _table_exists(db, "invites"):
            cursor = await db.execute(
                """
                SELECT COUNT(*)
                FROM invites
                WHERE LOWER(status) IN ('confirmed', 'accepted')
                  AND (from_user_id = ? OR to_user_id = ?)
                """,
                (user_id, user_id),
            )
            row = await cursor.fetchone()
            return int(row[0] if row and row[0] is not None else 0)
        return 0

    if criteria_type == "events_hosted_confirmed_count":
        if not await _table_exists(db, "events"):
            return 0
        columns = await _table_columns(db, "events")
        owner_col = next(
            (col for col in ("owner_id", "host_user_id", "organizer_user_id", "created_by_user_id", "user_id") if col in columns),
            None,
        )
        if owner_col is None:
            return 0
        status_filter = " AND LOWER(status) IN ('confirmed', 'accepted')" if "status" in columns else ""
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM events WHERE {owner_col} = ?{status_filter}",
            (user_id,),
        )
        row = await cursor.fetchone()
        return int(row[0] if row and row[0] is not None else 0)

    if criteria_type == "events_attended_confirmed_count":
        attendees_table = None
        if await _table_exists(db, "event_participants"):
            attendees_table = "event_participants"
        elif await _table_exists(db, "event_attendees"):
            attendees_table = "event_attendees"

        if attendees_table and await _table_exists(db, "events"):
            attendees_columns = await _table_columns(db, attendees_table)
            events_columns = await _table_columns(db, "events")
            if {"event_id", "user_id"}.issubset(attendees_columns):
                status_filter = " AND LOWER(e.status) IN ('confirmed', 'accepted')" if "status" in events_columns else ""
                attendance_filter = ""
                if "status" in attendees_columns:
                    attendance_filter = " AND LOWER(ea.status) IN ('attended', 'joined')"
                cursor = await db.execute(
                    f"""
                    SELECT COUNT(DISTINCT ea.event_id)
                    FROM {attendees_table} ea
                    JOIN events e ON e.id = ea.event_id
                    WHERE ea.user_id = ?{attendance_filter}{status_filter}
                    """,
                    (user_id,),
                )
                row = await cursor.fetchone()
                return int(row[0] if row and row[0] is not None else 0)
        return 0

    return 0
