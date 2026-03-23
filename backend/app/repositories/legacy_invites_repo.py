import aiosqlite


async def ensure_notifications_table(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            payload TEXT,
            read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )


async def get_invites_need_survey(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT
            i.id,
            i.from_user_id,
            i.to_user_id,
            i.place_name,
            i.meal_type,
            i.responded_at,
            fu.tg_id AS from_tg,
            tu.tg_id AS to_tg,
            COALESCE(fu.full_name, fu.name, fu.username, '') AS from_name,
            COALESCE(tu.full_name, tu.name, tu.username, '') AS to_name
        FROM invites i
        JOIN users fu ON fu.id = i.from_user_id
        JOIN users tu ON tu.id = i.to_user_id
        WHERE i.status = 'accepted'
          AND IFNULL(i.survey_sent, 0) = 0
          AND strftime('%s', replace(replace(i.responded_at,'T',' '),'Z','')) <= strftime('%s', 'now', '-1 hour')
        """
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def mark_survey_sent(db: aiosqlite.Connection, invite_id: int) -> bool:
    cursor = await db.execute(
        "UPDATE invites SET survey_sent = 1 WHERE id = ? AND IFNULL(survey_sent, 0) = 0",
        (invite_id,),
    )
    return cursor.rowcount > 0


async def insert_notification(
    db: aiosqlite.Connection,
    user_id: int,
    title: str,
    body: str,
    payload_json: str,
) -> None:
    await db.execute(
        """
        INSERT INTO notifications (user_id, type, payload, read, created_at)
        VALUES (?, ?, ?, 0, datetime('now'))
        """,
        (user_id, title or "survey", payload_json),
    )
