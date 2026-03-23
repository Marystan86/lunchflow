from datetime import datetime, timedelta

import aiosqlite
from fastapi import HTTPException

from backend.app.repositories import meeting_confirmations_repo, meeting_requests_repo, meetings_repo, users_repo
from backend.app.settings import settings
from backend.app.services import meeting_confirmation_service


SCENARIO_OUTGOING_ACCEPTED = "seed_o2o_outgoing_accepted"
SCENARIO_OUTGOING_PENDING = "seed_o2o_outgoing_pending"
SCENARIO_INCOMING_PENDING = "seed_o2o_incoming_pending"
SCENARIO_COMPLETED = "seed_o2o_completed"


def _iso_days_from_now(days: int) -> str:
    return (datetime.utcnow() + timedelta(days=days)).replace(microsecond=0).isoformat()


async def _ensure_base_users(db: aiosqlite.Connection) -> dict[int, dict]:
    names = {
        1: "Maydan",
        2: "Aidar Bekov",
        3: "Alina Seitova",
        4: "Nursultan Ibraev",
    }
    users: dict[int, dict] = {}
    for user_id, full_name in names.items():
        users[user_id] = await users_repo.ensure_dev_user(db, user_id=user_id, full_name=full_name)
    return users


async def _ensure_request(
    db: aiosqlite.Connection,
    *,
    from_user_id: int,
    to_user_id: int,
    scheduled_for: str,
    fmt: str,
    location: str | None,
    message: str,
    status: str,
) -> tuple[dict, bool]:
    row = await meeting_requests_repo.find_by_pair_and_message(
        db,
        from_user_id=int(from_user_id),
        to_user_id=int(to_user_id),
        message=message,
    )
    created = False
    if row is None:
        row = await meeting_requests_repo.create_request(
            db,
            from_user_id=int(from_user_id),
            to_user_id=int(to_user_id),
            scheduled_for=scheduled_for,
            format=fmt,
            location=location,
            message=message,
            expires_at=None,
        )
        created = True

    current_status = str(row.get("status") or "").lower()
    if current_status != status:
        row = await meeting_requests_repo.set_status(
            db,
            request_id=int(row["id"]),
            status=status,
            responder_user_id=int(to_user_id) if status in {"accepted", "declined", "expired"} else None,
        )
    return row, created


async def _ensure_meeting_for_request(
    db: aiosqlite.Connection,
    *,
    request_row: dict,
    force_status: str | None = None,
) -> tuple[dict, bool]:
    meeting = await meetings_repo.get_by_request_id(db, int(request_row["id"]))
    created = False
    if meeting is None:
        meeting = await meetings_repo.create_from_request(
            db,
            request_id=int(request_row["id"]),
            participant_a_id=int(request_row["from_user_id"]),
            participant_b_id=int(request_row["to_user_id"]),
            scheduled_for=str(request_row.get("scheduled_for") or datetime.utcnow().isoformat()),
            format=str(request_row.get("format") or "online"),
            location=request_row.get("location"),
            notes=request_row.get("message"),
        )
        created = True

    if force_status and str(meeting.get("status") or "").lower() != force_status:
        meeting = await meetings_repo.set_status(db, int(meeting["id"]), status=force_status) or meeting
    return meeting, created


async def _ensure_completed_with_confirmations(db: aiosqlite.Connection, *, meeting: dict) -> int:
    meeting_id = int(meeting["id"])
    participant_a = int(meeting.get("participant_a_id") or meeting.get("initiator_id"))
    participant_b = int(meeting.get("participant_b_id") or meeting.get("receiver_id"))
    confirmations = await meeting_confirmations_repo.list_for_meeting(db, meeting_id)
    existing = {(int(row["user_id"]), str(row["confirmation_status"])) for row in confirmations}
    created_count = 0

    if (participant_a, "met") not in existing:
        await meeting_confirmation_service.create_confirmation(
            db,
            meeting_id=meeting_id,
            user_id=participant_a,
            confirmation_status="met",
            comment="dev seed",
        )
        created_count += 1
    if (participant_b, "met") not in existing:
        await meeting_confirmation_service.create_confirmation(
            db,
            meeting_id=meeting_id,
            user_id=participant_b,
            confirmation_status="met",
            comment="dev seed",
        )
        created_count += 1

    return created_count


async def _count_visible_requests(db: aiosqlite.Connection, *, user_id: int, incoming: bool) -> int:
    if incoming:
        rows = await meeting_requests_repo.list_incoming(db, user_id=user_id, limit=200)
    else:
        rows = await meeting_requests_repo.list_outgoing(db, user_id=user_id, limit=200)

    count = 0
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status == "accepted":
            meeting = await meetings_repo.get_by_request_id(db, int(row["id"]))
            if meeting and str(meeting.get("status") or "").lower() in {"completed", "cancelled"}:
                continue
        count += 1
    return count


async def seed_one_on_one_test_data(
    db: aiosqlite.Connection,
    *,
    user_id: int = 1,
) -> dict:
    if settings.env != "dev":
        raise HTTPException(status_code=403, detail="seed is allowed only in dev")
    if int(user_id) != 1:
        raise HTTPException(status_code=400, detail="only Maydan (id=1) seed is supported")

    await _ensure_base_users(db)

    created_request_ids: list[int] = []
    created_meeting_ids: list[int] = []
    created_confirmations = 0

    req1, req1_created = await _ensure_request(
        db,
        from_user_id=1,
        to_user_id=2,
        scheduled_for=_iso_days_from_now(3),
        fmt="online",
        location=None,
        message=SCENARIO_OUTGOING_ACCEPTED,
        status="accepted",
    )
    if req1_created:
        created_request_ids.append(int(req1["id"]))
    meeting1, meeting1_created = await _ensure_meeting_for_request(db, request_row=req1, force_status="scheduled")
    if meeting1_created:
        created_meeting_ids.append(int(meeting1["id"]))

    req2, req2_created = await _ensure_request(
        db,
        from_user_id=1,
        to_user_id=3,
        scheduled_for=_iso_days_from_now(4),
        fmt="offline",
        location="Алматы",
        message=SCENARIO_OUTGOING_PENDING,
        status="pending",
    )
    if req2_created:
        created_request_ids.append(int(req2["id"]))

    req3, req3_created = await _ensure_request(
        db,
        from_user_id=4,
        to_user_id=1,
        scheduled_for=_iso_days_from_now(2),
        fmt="online",
        location=None,
        message=SCENARIO_INCOMING_PENDING,
        status="pending",
    )
    if req3_created:
        created_request_ids.append(int(req3["id"]))

    req4, req4_created = await _ensure_request(
        db,
        from_user_id=1,
        to_user_id=2,
        scheduled_for=_iso_days_from_now(-5),
        fmt="offline",
        location="Астана",
        message=SCENARIO_COMPLETED,
        status="accepted",
    )
    if req4_created:
        created_request_ids.append(int(req4["id"]))
    meeting4, meeting4_created = await _ensure_meeting_for_request(db, request_row=req4)
    if meeting4_created:
        created_meeting_ids.append(int(meeting4["id"]))
    created_confirmations += await _ensure_completed_with_confirmations(db, meeting=meeting4)

    await db.commit()

    outgoing_count = await _count_visible_requests(db, user_id=1, incoming=False)
    incoming_count = await _count_visible_requests(db, user_id=1, incoming=True)

    return {
        "user_id": 1,
        "created_request_ids": created_request_ids,
        "created_meeting_ids": created_meeting_ids,
        "created_confirmations": int(created_confirmations),
        "scenario_ids": {
            "outgoing_accepted_request_id": int(req1["id"]),
            "outgoing_accepted_meeting_id": int(meeting1["id"]),
            "outgoing_pending_request_id": int(req2["id"]),
            "incoming_pending_request_id": int(req3["id"]),
            "completed_request_id": int(req4["id"]),
            "completed_meeting_id": int(meeting4["id"]),
        },
        "counts": {
            "outgoing_requests": int(outgoing_count),
            "incoming_requests": int(incoming_count),
        },
    }
