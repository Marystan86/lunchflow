from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_current_user
from backend.app.db import get_db
from backend.app.models.schemas import MeetingRequestApiCreate
from backend.app.repositories import meeting_requests_repo
from backend.app.services import meeting_request_service


router = APIRouter(prefix="/meeting-requests")


def _to_item(row: dict, *, request_type: str) -> dict:
    subtitle = "Входящий запрос 1-на-1" if request_type == "incoming" else "Запрос на встречу 1-на-1"
    return {
        "id": int(row["id"]),
        "request_id": int(row["id"]),
        "title": row.get("counterpart_name") or "Участник",
        "subtitle": subtitle,
        "status": str(row.get("status") or "pending"),
        "scheduled_for": row.get("scheduled_for"),
        "format": row.get("format"),
        "location": row.get("location"),
        "message": row.get("message"),
        "from_user_id": int(row.get("from_user_id") or 0),
        "to_user_id": int(row.get("to_user_id") or 0),
    }


@router.post("")
async def create_meeting_request(
    payload: MeetingRequestApiCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    scheduled_for = payload.proposed_time.replace(second=0, microsecond=0).isoformat()
    request_row = await meeting_request_service.create_request(
        db,
        from_user_id=int(current_user["id"]),
        payload={
            "to_user_id": int(payload.to_user_id),
            "scheduled_for": scheduled_for,
            "format": payload.format,
            "location": None,
            "message": payload.message,
            "expires_at": None,
        },
    )
    await db.commit()
    return {"ok": True, "request_id": int(request_row["id"]), "request": _to_item(request_row, request_type="outgoing")}


@router.get("")
async def list_meeting_requests(
    type: str = Query(default="incoming", pattern="^(incoming|outgoing)$"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    rows = await meeting_requests_repo.list_by_type(
        db,
        user_id=int(current_user["id"]),
        request_type=type,
        only_pending=(type == "incoming"),
        limit=int(limit),
    )
    items = [_to_item(row, request_type=type) for row in rows]
    return {"type": type, "count": len(items), "items": items}


@router.post("/{request_id}/accept")
async def accept_meeting_request(
    request_id: int,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    result = await meeting_request_service.respond_request(
        db,
        request_id=int(request_id),
        actor_user_id=int(current_user["id"]),
        action="accept",
    )
    await db.commit()
    request_row = result.get("request") or {}
    meeting = result.get("meeting") or {}
    return {
        "ok": True,
        "request_id": int(request_row.get("id") or request_id),
        "meeting_id": int(meeting.get("id") or 0),
        "request_status": str(request_row.get("status") or "accepted"),
        "meeting_status": str(meeting.get("status") or "scheduled"),
        "request": _to_item(request_row, request_type="incoming") if request_row else None,
    }
