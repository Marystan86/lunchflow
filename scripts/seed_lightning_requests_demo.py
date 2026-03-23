import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import aiosqlite


DEMO_PREFIX = "[DEMO-LIGHTNING]"


def _ensure_project_root_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def _iso_in_days(days: int, hour: int, minute: int = 0) -> str:
    dt = datetime.utcnow() + timedelta(days=days)
    dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return dt.isoformat()


async def _cleanup_demo_requests(db: aiosqlite.Connection) -> dict:
    cur = await db.execute(
        """
        SELECT id
        FROM meeting_requests
        WHERE message LIKE ?
        """,
        (f"{DEMO_PREFIX}%",),
    )
    request_ids = [int(row[0]) for row in await cur.fetchall()]
    if not request_ids:
        return {"meeting_requests_deleted": 0, "meetings_deleted": 0, "confirmations_deleted": 0}

    placeholders = ",".join(["?"] * len(request_ids))
    cur = await db.execute(
        f"""
        SELECT id
        FROM meetings
        WHERE request_id IN ({placeholders})
        """,
        tuple(request_ids),
    )
    meeting_ids = [int(row[0]) for row in await cur.fetchall()]

    confirmations_deleted = 0
    if meeting_ids:
        meeting_placeholders = ",".join(["?"] * len(meeting_ids))
        cur = await db.execute(
            f"DELETE FROM meeting_confirmations WHERE meeting_id IN ({meeting_placeholders})",
            tuple(meeting_ids),
        )
        confirmations_deleted = int(cur.rowcount or 0)

    cur = await db.execute(
        f"DELETE FROM meetings WHERE request_id IN ({placeholders})",
        tuple(request_ids),
    )
    meetings_deleted = int(cur.rowcount or 0)

    cur = await db.execute(
        f"DELETE FROM meeting_requests WHERE id IN ({placeholders})",
        tuple(request_ids),
    )
    requests_deleted = int(cur.rowcount or 0)

    return {
        "meeting_requests_deleted": requests_deleted,
        "meetings_deleted": meetings_deleted,
        "confirmations_deleted": confirmations_deleted,
    }


async def _insert_request(
    db: aiosqlite.Connection,
    *,
    from_user_id: int,
    to_user_id: int,
    scheduled_for: str,
    format_value: str,
    location: str | None,
    status: str,
    message: str,
) -> int | None:
    now_iso = datetime.utcnow().isoformat()
    responder_user_id = None
    responded_at = None
    if status in {"accepted", "declined", "cancelled", "expired"}:
        responder_user_id = int(to_user_id)
        responded_at = now_iso

    try:
        cur = await db.execute(
            """
            INSERT INTO meeting_requests (
                from_user_id, to_user_id, scheduled_for, format, location, message, status,
                expires_at, responder_user_id, responded_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(from_user_id),
                int(to_user_id),
                scheduled_for,
                format_value,
                location,
                message,
                status,
                None,
                responder_user_id,
                responded_at,
                now_iso,
                now_iso,
            ),
        )
    except Exception:
        return None
    return int(cur.lastrowid)


async def _insert_meeting_from_request(
    db: aiosqlite.Connection,
    *,
    request_id: int,
    participant_a_id: int,
    participant_b_id: int,
    scheduled_for: str,
    format_value: str,
    location: str | None,
    notes: str,
) -> int | None:
    now_iso = datetime.utcnow().isoformat()
    try:
        cur = await db.execute(
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
                format_value,
                location,
                notes,
                now_iso,
            ),
        )
    except Exception:
        return None
    return int(cur.lastrowid)


async def seed_lightning_requests(clear_demo: bool = True) -> dict:
    _ensure_project_root_on_path()
    from backend.app.db import init_db
    from backend.app.settings import settings

    await init_db()

    stats = {
        "users_total": 0,
        "targets_total": 0,
        "cleanup": {},
        "requests_created": 0,
        "meetings_created": 0,
    }

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row

        if clear_demo:
            stats["cleanup"] = await _cleanup_demo_requests(db)

        cur = await db.execute(
            """
            SELECT id, source
            FROM users
            WHERE COALESCE(status, 'active') != 'suspended'
            ORDER BY id
            """
        )
        users = [dict(row) for row in await cur.fetchall()]
        user_ids = [int(u["id"]) for u in users]
        stats["users_total"] = len(user_ids)
        if len(user_ids) < 2:
            await db.commit()
            return stats

        sample_pool = [int(u["id"]) for u in users if str(u.get("source") or "") == "sample"]
        if len(sample_pool) < 2:
            sample_pool = user_ids[:]

        target_ids = [int(u["id"]) for u in users if str(u.get("source") or "") != "sample"]
        if not target_ids:
            target_ids = sample_pool[: min(len(sample_pool), 10)]
        stats["targets_total"] = len(target_ids)

        rnd = random.Random(999)
        for idx, target_id in enumerate(target_ids):
            peers = [uid for uid in sample_pool if uid != target_id]
            if len(peers) < 3:
                peers = [uid for uid in user_ids if uid != target_id]
            if len(peers) < 2:
                continue
            rnd.shuffle(peers)

            outgoing_peer = peers[0]
            incoming_peer = peers[1]
            accepted_peer = peers[2] if len(peers) > 2 else peers[0]

            fmt_out = "online" if idx % 2 == 0 else "offline"
            loc_out = None if fmt_out == "online" else "Алматы"
            out_req_id = await _insert_request(
                db,
                from_user_id=target_id,
                to_user_id=outgoing_peer,
                scheduled_for=_iso_in_days(2 + (idx % 4), 19),
                format_value=fmt_out,
                location=loc_out,
                status="pending",
                message=f"{DEMO_PREFIX} Исходящий запрос для демо-экрана",
            )
            if out_req_id:
                stats["requests_created"] += 1

            fmt_in = "offline" if idx % 2 == 0 else "online"
            loc_in = "Астана" if fmt_in == "offline" else None
            in_req_id = await _insert_request(
                db,
                from_user_id=incoming_peer,
                to_user_id=target_id,
                scheduled_for=_iso_in_days(3 + (idx % 3), 18, 30),
                format_value=fmt_in,
                location=loc_in,
                status="pending",
                message=f"{DEMO_PREFIX} Входящий запрос для демо-экрана",
            )
            if in_req_id:
                stats["requests_created"] += 1

            acc_fmt = "online"
            acc_req_id = await _insert_request(
                db,
                from_user_id=target_id,
                to_user_id=accepted_peer,
                scheduled_for=_iso_in_days(1 + (idx % 2), 12, 0),
                format_value=acc_fmt,
                location=None,
                status="accepted",
                message=f"{DEMO_PREFIX} Accepted пример для демо-экрана",
            )
            if acc_req_id:
                stats["requests_created"] += 1
                meeting_id = await _insert_meeting_from_request(
                    db,
                    request_id=int(acc_req_id),
                    participant_a_id=int(target_id),
                    participant_b_id=int(accepted_peer),
                    scheduled_for=_iso_in_days(1 + (idx % 2), 12, 0),
                    format_value=acc_fmt,
                    location=None,
                    notes=f"{DEMO_PREFIX} Встреча из accepted-запроса",
                )
                if meeting_id:
                    stats["meetings_created"] += 1

        await db.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo 1-on-1 meeting requests for Lightning screen.")
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear previous demo lightning requests before insert.",
    )
    args = parser.parse_args()

    _ensure_project_root_on_path()
    stats = asyncio.run(seed_lightning_requests(clear_demo=not args.no_clear))
    print("Lightning requests demo seed completed.")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

