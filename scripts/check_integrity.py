import asyncio
import sys
from pathlib import Path

import aiosqlite


REQUIRED_TABLES = [
    "users",
    "meetings",
    "events",
    "event_participants",
    "points_ledger",
    "badges",
    "user_badges",
    "badge_votes",
    "news",
]


def _ensure_project_root_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


async def _table_exists(db: aiosqlite.Connection, table_name: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    )
    return (await cursor.fetchone()) is not None


async def _scalar(db: aiosqlite.Connection, query: str, params: tuple = ()) -> int:
    cursor = await db.execute(query, params)
    row = await cursor.fetchone()
    return int(row[0] if row and row[0] is not None else 0)


async def main() -> int:
    _ensure_project_root_on_path()
    from backend.app.settings import settings

    print(f"DB: {settings.db_path}")
    print("Table checks:")

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row

        table_status: dict[str, bool] = {}
        for table in REQUIRED_TABLES:
            exists = await _table_exists(db, table)
            table_status[table] = exists
            state = "OK" if exists else "FAIL"
            print(f"  - {table}: {state}")

        all_tables_ok = all(table_status.values())

        counts = {
            "users_sample_count": 0,
            "meetings_between_sample_count": 0,
            "points_for_sample_count": 0,
            "badges_catalog_count": 0,
            "user_badges_for_sample_count": 0,
            "badge_votes_for_sample_count": 0,
            "news_total_count": 0,
            "news_linked_events_count": 0,
        }

        if table_status["users"]:
            counts["users_sample_count"] = await _scalar(
                db,
                "SELECT COUNT(*) FROM users WHERE source='sample'",
            )

        if table_status["users"] and table_status["meetings"]:
            counts["meetings_between_sample_count"] = await _scalar(
                db,
                """
                SELECT COUNT(*)
                FROM meetings m
                JOIN users u1 ON u1.id = m.initiator_id
                JOIN users u2 ON u2.id = m.receiver_id
                WHERE u1.source='sample' AND u2.source='sample'
                """,
            )

        if table_status["users"] and table_status["points_ledger"]:
            counts["points_for_sample_count"] = await _scalar(
                db,
                """
                SELECT COUNT(*)
                FROM points_ledger pl
                JOIN users u ON u.id = pl.user_id
                WHERE u.source='sample'
                """,
            )

        if table_status["badges"]:
            counts["badges_catalog_count"] = await _scalar(
                db,
                "SELECT COUNT(*) FROM badges",
            )

        if table_status["users"] and table_status["user_badges"]:
            counts["user_badges_for_sample_count"] = await _scalar(
                db,
                """
                SELECT COUNT(*)
                FROM user_badges ub
                JOIN users u ON u.id = ub.user_id
                WHERE u.source='sample'
                """,
            )

        if table_status["users"] and table_status["badge_votes"]:
            counts["badge_votes_for_sample_count"] = await _scalar(
                db,
                """
                SELECT COUNT(*)
                FROM badge_votes bv
                JOIN users uf ON uf.id = bv.from_user_id
                JOIN users ut ON ut.id = bv.to_user_id
                WHERE uf.source='sample' AND ut.source='sample'
                """,
            )

        if table_status["news"]:
            counts["news_total_count"] = await _scalar(db, "SELECT COUNT(*) FROM news")
            counts["news_linked_events_count"] = await _scalar(
                db,
                "SELECT COUNT(*) FROM news WHERE entity_type='event' AND entity_id IS NOT NULL",
            )

    print("Counts:")
    for key, value in counts.items():
        print(f"  - {key}: {value}")

    key_counts_positive = all(value > 0 for value in counts.values())
    passed = all_tables_ok and key_counts_positive

    print(f"RESULT: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
