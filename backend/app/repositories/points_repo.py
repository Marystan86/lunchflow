import aiosqlite


async def create_ledger_entry(
    db: aiosqlite.Connection,
    *,
    user_id: int,
    amount: int,
    reason_type: str,
    entity_type: str | None,
    entity_id: int | None,
    meta: str | None,
    created_at: str,
) -> int:
    cursor = await db.execute(
        """
        INSERT INTO points_ledger (
            user_id, amount, reason_type, entity_type, entity_id, meta, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(user_id),
            int(amount),
            reason_type,
            entity_type,
            entity_id,
            meta,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


async def get_balance(db: aiosqlite.Connection, user_id: int) -> int:
    cursor = await db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM points_ledger WHERE user_id = ?",
        (int(user_id),),
    )
    row = await cursor.fetchone()
    return int(row[0] if row and row[0] is not None else 0)


async def has_ledger_entry(
    db: aiosqlite.Connection,
    *,
    user_id: int,
    reason_type: str,
    entity_type: str | None,
    entity_id: int | None,
) -> bool:
    cursor = await db.execute(
        """
        SELECT 1
        FROM points_ledger
        WHERE user_id = ? AND reason_type = ? AND entity_type IS ? AND entity_id IS ?
        LIMIT 1
        """,
        (int(user_id), reason_type, entity_type, entity_id),
    )
    return (await cursor.fetchone()) is not None
