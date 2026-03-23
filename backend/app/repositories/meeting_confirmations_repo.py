from datetime import datetime

import aiosqlite


async def create_confirmation(
    db: aiosqlite.Connection,
    *,
    meeting_id: int,
    user_id: int,
    confirmation_status: str,
    comment: str | None,
) -> bool:
    cursor = await db.execute(
        """
        INSERT OR IGNORE INTO meeting_confirmations (
            meeting_id, user_id, confirmation_status, comment, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            int(meeting_id),
            int(user_id),
            confirmation_status,
            comment,
            datetime.utcnow().isoformat(),
        ),
    )
    return cursor.rowcount > 0


async def list_for_meeting(db: aiosqlite.Connection, meeting_id: int) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT *
        FROM meeting_confirmations
        WHERE meeting_id = ?
        ORDER BY created_at ASC
        """,
        (int(meeting_id),),
    )
    return [dict(row) for row in await cursor.fetchall()]
