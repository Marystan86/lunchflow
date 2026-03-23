from datetime import datetime

import aiosqlite


async def create_request(
    db: aiosqlite.Connection,
    *,
    from_user_id: int,
    to_user_id: int,
    scheduled_for: str,
    format: str,
    location: str | None,
    message: str | None,
    expires_at: str | None,
) -> dict:
    now_iso = datetime.utcnow().isoformat()
    cursor = await db.execute(
        """
        INSERT INTO meeting_requests (
            from_user_id, to_user_id, scheduled_for, format, location, message, status,
            expires_at, responder_user_id, responded_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, NULL, NULL, ?, ?)
        """,
        (
            int(from_user_id),
            int(to_user_id),
            scheduled_for,
            format,
            location,
            message,
            expires_at,
            now_iso,
            now_iso,
        ),
    )
    return await get_by_id(db, int(cursor.lastrowid))


async def get_by_id(db: aiosqlite.Connection, request_id: int) -> dict | None:
    cursor = await db.execute("SELECT * FROM meeting_requests WHERE id = ? LIMIT 1", (int(request_id),))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def set_status(
    db: aiosqlite.Connection,
    *,
    request_id: int,
    status: str,
    responder_user_id: int | None,
) -> dict | None:
    now_iso = datetime.utcnow().isoformat()
    await db.execute(
        """
        UPDATE meeting_requests
        SET status = ?, responder_user_id = ?, responded_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, responder_user_id, now_iso, now_iso, int(request_id)),
    )
    return await get_by_id(db, int(request_id))


async def list_outgoing(db: aiosqlite.Connection, user_id: int, limit: int = 50) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT mr.*, u.full_name AS counterpart_name
        FROM meeting_requests mr
        JOIN users u ON u.id = mr.to_user_id
        WHERE mr.from_user_id = ?
        ORDER BY mr.created_at DESC
        LIMIT ?
        """,
        (int(user_id), int(limit)),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def list_incoming(db: aiosqlite.Connection, user_id: int, limit: int = 50) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT mr.*, u.full_name AS counterpart_name
        FROM meeting_requests mr
        JOIN users u ON u.id = mr.from_user_id
        WHERE mr.to_user_id = ?
        ORDER BY mr.created_at DESC
        LIMIT ?
        """,
        (int(user_id), int(limit)),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def list_recent_requests(db: aiosqlite.Connection, limit: int = 50) -> list[dict]:
    cursor = await db.execute(
        """
        SELECT
            mr.*,
            uf.full_name AS from_user_name,
            ut.full_name AS to_user_name
        FROM meeting_requests mr
        JOIN users uf ON uf.id = mr.from_user_id
        JOIN users ut ON ut.id = mr.to_user_id
        ORDER BY mr.created_at DESC, mr.id DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def find_by_pair_and_message(
    db: aiosqlite.Connection,
    *,
    from_user_id: int,
    to_user_id: int,
    message: str,
) -> dict | None:
    cursor = await db.execute(
        """
        SELECT *
        FROM meeting_requests
        WHERE from_user_id = ? AND to_user_id = ? AND message = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (int(from_user_id), int(to_user_id), str(message)),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def find_active_between_users(
    db: aiosqlite.Connection,
    *,
    user_a_id: int,
    user_b_id: int,
) -> dict | None:
    cursor = await db.execute(
        """
        SELECT *
        FROM meeting_requests
        WHERE (
            (from_user_id = ? AND to_user_id = ?)
            OR (from_user_id = ? AND to_user_id = ?)
        )
        AND status IN ('pending', 'accepted')
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (int(user_a_id), int(user_b_id), int(user_b_id), int(user_a_id)),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_by_type(
    db: aiosqlite.Connection,
    *,
    user_id: int,
    request_type: str,
    only_pending: bool = False,
    limit: int = 50,
) -> list[dict]:
    if request_type == "incoming":
        base_sql = """
            SELECT mr.*, u.full_name AS counterpart_name
            FROM meeting_requests mr
            JOIN users u ON u.id = mr.from_user_id
            WHERE mr.to_user_id = ?
        """
    else:
        base_sql = """
            SELECT mr.*, u.full_name AS counterpart_name
            FROM meeting_requests mr
            JOIN users u ON u.id = mr.to_user_id
            WHERE mr.from_user_id = ?
        """
    params: list = [int(user_id)]
    if only_pending:
        base_sql += " AND mr.status = 'pending'"
    base_sql += " ORDER BY mr.created_at DESC, mr.id DESC LIMIT ?"
    params.append(int(limit))
    cursor = await db.execute(base_sql, tuple(params))
    return [dict(row) for row in await cursor.fetchall()]
