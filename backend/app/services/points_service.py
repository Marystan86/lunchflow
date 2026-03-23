import json
from datetime import datetime
from typing import Any

import aiosqlite

from backend.app.repositories import points_repo


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


async def add_points(
    db: aiosqlite.Connection,
    *,
    user_id: int,
    amount: int,
    reason_type: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> int:
    meta_json = json.dumps(meta, ensure_ascii=False) if meta is not None else None
    return await points_repo.create_ledger_entry(
        db,
        user_id=user_id,
        amount=amount,
        reason_type=reason_type,
        entity_type=entity_type,
        entity_id=entity_id,
        meta=meta_json,
        created_at=_utc_iso(),
    )


async def get_user_balance(db: aiosqlite.Connection, user_id: int) -> int:
    return await points_repo.get_balance(db, user_id)
