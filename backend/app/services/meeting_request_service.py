from fastapi import HTTPException

import aiosqlite

from backend.app.repositories import meeting_requests_repo, meetings_repo, users_repo


VALID_REQUEST_STATUSES = {"pending", "accepted", "declined", "cancelled", "expired"}


async def create_request(db, *, from_user_id: int, payload: dict) -> dict:
    if int(from_user_id) == int(payload["to_user_id"]):
        raise HTTPException(status_code=400, detail="нельзя отправить запрос самому себе")
    if payload.get("format") not in {"online", "offline"}:
        raise HTTPException(status_code=400, detail="format должен быть online или offline")
    receiver = await users_repo.get_by_id(db, int(payload["to_user_id"]))
    if receiver is None:
        raise HTTPException(status_code=404, detail="пользователь не найден")
    active = await meeting_requests_repo.find_active_between_users(
        db,
        user_a_id=int(from_user_id),
        user_b_id=int(payload["to_user_id"]),
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="уже есть активный запрос")
    try:
        row = await meeting_requests_repo.create_request(
            db,
            from_user_id=int(from_user_id),
            to_user_id=int(payload["to_user_id"]),
            scheduled_for=str(payload["scheduled_for"]),
            format=str(payload["format"]),
            location=payload.get("location"),
            message=payload.get("message"),
            expires_at=payload.get("expires_at"),
        )
    except aiosqlite.IntegrityError as exc:
        err = str(exc).lower()
        if "unique" in err:
            raise HTTPException(status_code=409, detail="уже есть активный запрос") from exc
        if "foreign key" in err:
            raise HTTPException(status_code=404, detail="пользователь не найден") from exc
        raise HTTPException(status_code=400, detail="ошибка данных meeting request") from exc
    return row


async def respond_request(db, *, request_id: int, actor_user_id: int, action: str) -> dict:
    if action not in {"accept", "decline", "cancel", "expire"}:
        raise HTTPException(status_code=400, detail="invalid action")

    request_row = await meeting_requests_repo.get_by_id(db, int(request_id))
    if request_row is None:
        raise HTTPException(status_code=404, detail="meeting request not found")

    current_status = str(request_row.get("status") or "").lower()
    if current_status != "pending":
        raise HTTPException(status_code=400, detail=f"request already {current_status}")

    if action in {"accept", "decline", "expire"}:
        if int(request_row["to_user_id"]) != int(actor_user_id):
            raise HTTPException(status_code=403, detail="only receiver can perform this action")
    elif action == "cancel":
        if int(request_row["from_user_id"]) != int(actor_user_id):
            raise HTTPException(status_code=403, detail="only sender can cancel request")

    mapped_status = {
        "accept": "accepted",
        "decline": "declined",
        "cancel": "cancelled",
        "expire": "expired",
    }[action]
    updated = await meeting_requests_repo.set_status(
        db,
        request_id=int(request_id),
        status=mapped_status,
        responder_user_id=int(actor_user_id),
    )

    meeting = None
    if mapped_status == "accepted":
        existing_meeting = await meetings_repo.get_by_request_id(db, int(request_id))
        if existing_meeting is None:
            meeting = await meetings_repo.create_from_request(
                db,
                request_id=int(request_id),
                participant_a_id=int(request_row["from_user_id"]),
                participant_b_id=int(request_row["to_user_id"]),
                scheduled_for=str(request_row.get("scheduled_for") or request_row.get("created_at")),
                format=str(request_row.get("format") or "online"),
                location=request_row.get("location"),
                notes=request_row.get("message"),
            )
        else:
            meeting = existing_meeting

    return {"request": updated, "meeting": meeting}
