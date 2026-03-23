from datetime import datetime

import aiosqlite


async def create_from_request(
    db: aiosqlite.Connection,
    *,
    request_id: int,
    participant_a_id: int,
    participant_b_id: int,
    scheduled_for: str,
    format: str,
    location: str | None,
    notes: str | None,
) -> dict:
    now_iso = datetime.utcnow().isoformat()
    cursor = await db.execute(
        """
        INSERT INTO meetings (
            initiator_id, receiver_id, request_id, participant_a_id, participant_b_id,
            scheduled_for, format, location, notes, status, created_at, confirmed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, NULL)
        """,
        (
            int(participant_a_id),
            int(participant_b_id),
            int(request_id),
            int(participant_a_id),
            int(participant_b_id),
            scheduled_for,
            format,
            location,
            notes,
            now_iso,
        ),
    )
    return await get_by_id(db, int(cursor.lastrowid))


async def get_by_id(db: aiosqlite.Connection, meeting_id: int) -> dict | None:
    cursor = await db.execute("SELECT * FROM meetings WHERE id = ? LIMIT 1", (int(meeting_id),))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_by_request_id(db: aiosqlite.Connection, request_id: int) -> dict | None:
    cursor = await db.execute("SELECT * FROM meetings WHERE request_id = ? LIMIT 1", (int(request_id),))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def set_status(db: aiosqlite.Connection, meeting_id: int, status: str) -> dict | None:
    now_iso = datetime.utcnow().isoformat()
    completed_at = now_iso if status == "completed" else None
    cancelled_at = now_iso if status == "cancelled" else None
    await db.execute(
        """
        UPDATE meetings
        SET status = ?, completed_at = COALESCE(?, completed_at), cancelled_at = COALESCE(?, cancelled_at)
        WHERE id = ?
        """,
        (status, completed_at, cancelled_at, int(meeting_id)),
    )
    return await get_by_id(db, int(meeting_id))


async def list_user_meetings(db: aiosqlite.Connection, user_id: int, limit: int = 100) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT *
        FROM meetings
        WHERE participant_a_id = ? OR participant_b_id = ? OR initiator_id = ? OR receiver_id = ?
        ORDER BY COALESCE(scheduled_for, created_at) DESC, id DESC
        LIMIT ?
        """,
        (int(user_id), int(user_id), int(user_id), int(user_id), int(limit)),
    )
    return [dict(row) for row in await cursor.fetchall()]
