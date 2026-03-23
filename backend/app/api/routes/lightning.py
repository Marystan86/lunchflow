from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.deps import get_current_user, require_admin
from backend.app.db import get_db
from backend.app.repositories import meeting_requests_repo
from backend.app.repositories import meetings_repo
from backend.app.models.schemas import (
    EventCreateRequest,
    LightningDashboardResponse,
    MeetingConfirmationCreate,
    MeetingRequestCreate,
    MeetingRequestRespond,
)
from backend.app.services import (
    lightning_dashboard_service,
    lightning_event_service,
    meeting_confirmation_service,
    meeting_request_service,
    one_on_one_seed_service,
)
from backend.app.settings import settings


router = APIRouter(prefix="/lightning")


def _ensure_feature_enabled() -> None:
    if not settings.use_new_meeting_model:
        raise HTTPException(status_code=503, detail="new meeting model disabled")


async def _filter_request_rows_for_list(db, rows: list[dict]) -> list[dict]:
    filtered: list[dict] = []
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status == "accepted":
            meeting = await meetings_repo.get_by_request_id(db, int(row["id"]))
            if meeting and str(meeting.get("status") or "").lower() in {"completed", "cancelled"}:
                continue
        filtered.append(row)
    return filtered


@router.get("/dashboard", response_model=LightningDashboardResponse)
async def get_dashboard(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> LightningDashboardResponse:
    _ensure_feature_enabled()
    payload = await lightning_dashboard_service.build_dashboard(db, user_id=int(current_user["id"]), limit=int(limit))
    return LightningDashboardResponse(**payload)


@router.get("/public/dashboard", response_model=LightningDashboardResponse)
async def get_public_dashboard(
    limit: int = Query(default=50, ge=1, le=100),
    db=Depends(get_db),
) -> LightningDashboardResponse:
    _ensure_feature_enabled()
    payload = await lightning_dashboard_service.build_public_dashboard(db, limit=int(limit))
    return LightningDashboardResponse(**payload)


@router.get("/requests")
async def get_requests(
    type: str = Query(default="outgoing", pattern="^(outgoing|incoming)$"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_feature_enabled()
    user_id = int(current_user["id"])
    if type == "incoming":
        rows = await meeting_requests_repo.list_incoming(db, user_id=user_id, limit=int(limit))
        subtitle = "Входящий запрос 1-на-1"
    else:
        rows = await meeting_requests_repo.list_outgoing(db, user_id=user_id, limit=int(limit))
        subtitle = "Запрос на встречу 1-на-1"
    rows = await _filter_request_rows_for_list(db, rows)
    items = [
        {
            "id": int(row["id"]),
            "title": row.get("counterpart_name") or "Участник",
            "subtitle": subtitle,
            "status": str(row.get("status") or "pending"),
            "scheduled_for": row.get("scheduled_for"),
            "format": row.get("format"),
            "location": row.get("location"),
            "message": row.get("message"),
        }
        for row in rows
    ]
    return {"type": type, "count": len(items), "items": items}


@router.post("/requests")
async def create_request(
    payload: MeetingRequestCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_feature_enabled()
    request_row = await meeting_request_service.create_request(
        db,
        from_user_id=int(current_user["id"]),
        payload=payload.model_dump(),
    )
    await db.commit()
    return {"ok": True, "request": request_row}


@router.post("/requests/{request_id}/respond")
async def respond_request(
    request_id: int,
    payload: MeetingRequestRespond,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_feature_enabled()
    result = await meeting_request_service.respond_request(
        db,
        request_id=int(request_id),
        actor_user_id=int(current_user["id"]),
        action=payload.action,
    )
    await db.commit()
    return {"ok": True, **result}


@router.post("/meetings/{meeting_id}/confirm")
async def confirm_meeting(
    meeting_id: int,
    payload: MeetingConfirmationCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_feature_enabled()
    result = await meeting_confirmation_service.create_confirmation(
        db,
        meeting_id=int(meeting_id),
        user_id=int(current_user["id"]),
        confirmation_status=payload.confirmation_status,
        comment=payload.comment,
    )
    await db.commit()
    return {"ok": True, **result}


@router.post("/events")
async def create_user_event(
    payload: EventCreateRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_feature_enabled()
    event = await lightning_event_service.create_user_event(
        db,
        creator_user_id=int(current_user["id"]),
        payload=payload.model_dump(),
    )
    await db.commit()
    return {"ok": True, "event": event}


@router.post("/events/club")
async def create_club_event(
    payload: EventCreateRequest,
    admin_user: dict = Depends(require_admin),
    db=Depends(get_db),
) -> dict:
    _ensure_feature_enabled()
    event = await lightning_event_service.create_club_event(
        db,
        owner_user_id=int(admin_user["id"]),
        payload=payload.model_dump(),
    )
    await db.commit()
    return {"ok": True, "event": event}


@router.post("/events/{event_id}/join")
async def join_event(
    event_id: int,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_feature_enabled()
    result = await lightning_event_service.join_event(db, event_id=int(event_id), user_id=int(current_user["id"]))
    await db.commit()
    return {"ok": True, **result}


@router.post("/events/{event_id}/leave")
async def leave_event(
    event_id: int,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_feature_enabled()
    result = await lightning_event_service.leave_event(db, event_id=int(event_id), user_id=int(current_user["id"]))
    await db.commit()
    return {"ok": True, **result}


@router.post("/dev/seed-one-on-one")
async def seed_one_on_one_data(
    user_id: int = Query(default=1, ge=1),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    _ensure_feature_enabled()
    if settings.env != "dev":
        raise HTTPException(status_code=403, detail="seed is allowed only in dev")
    result = await one_on_one_seed_service.seed_one_on_one_test_data(db, user_id=int(user_id))
    await db.commit()
    return {"ok": True, "actor_user_id": int(current_user["id"]), **result}
