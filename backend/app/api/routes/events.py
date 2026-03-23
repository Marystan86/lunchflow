import traceback

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.app.api.deps import get_current_user, get_optional_current_user, require_admin
from backend.app.db import get_db
from backend.app.models.schemas import EventCreateRequest
from backend.app.services import events_service, lightning_event_service


router = APIRouter(prefix="/events")


class MemberEventCreateRequest(BaseModel):
    title: str
    description: str
    starts_at: str
    event_type: str = Field(pattern="^(online|offline)$")
    city: str | None = None
    location: str | None = None
    capacity: int = 6
    category: str | None = None
    tags: list[str] | None = None


@router.get("/permissions")
async def get_events_permissions(current_user: dict | None = Depends(get_optional_current_user)) -> dict:
    if not current_user:
        return {"can_create_member_event": False, "reason": "Войдите в приложение"}
    return {"can_create_member_event": True, "reason": None}


@router.post("/member")
async def create_member_event(
    payload: MemberEventCreateRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> dict:
    try:
        event = await events_service.create_member_event(
            db,
            payload=payload.model_dump(),
            current_user=current_user,
        )
        await db.commit()
        return {"ok": True, "event": event}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": str(e)})


@router.post("/club")
async def create_club_event(
    payload: EventCreateRequest,
    admin_user: dict = Depends(require_admin),
    db=Depends(get_db),
) -> dict:
    event = await lightning_event_service.create_club_event(
        db,
        owner_user_id=int(admin_user["id"]),
        payload=payload.model_dump(),
    )
    await db.commit()
    return {"ok": True, "event": event}
