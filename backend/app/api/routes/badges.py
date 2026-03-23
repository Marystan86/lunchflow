from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import get_current_user
from backend.app.models.schemas import BadgeItem, BadgeVoteRequest, BadgeVoteResponse
from backend.app.services import badges_service


router = APIRouter(prefix="/badges")


@router.get("", response_model=list[BadgeItem])
async def get_badges_catalog(_: dict = Depends(get_current_user)) -> list[BadgeItem]:
    rows = await badges_service.get_catalog()
    return [BadgeItem(**row) for row in rows]


@router.get("/me", response_model=list[BadgeItem])
async def get_my_badges(current_user: dict = Depends(get_current_user)) -> list[BadgeItem]:
    rows = await badges_service.get_my_badges(int(current_user["id"]))
    return [BadgeItem(**row) for row in rows]


@router.post("/vote", response_model=BadgeVoteResponse)
async def vote_badge(payload: BadgeVoteRequest, current_user: dict = Depends(get_current_user)) -> BadgeVoteResponse:
    if (current_user.get("status") or "").lower() != "active":
        raise HTTPException(status_code=403, detail="only active users can vote for badges")

    result = await badges_service.vote_badge(
        from_user_id=int(current_user["id"]),
        to_user_id=int(payload.to_user_id),
        badge_code=payload.badge_code,
        meeting_id=int(payload.meeting_id),
        comment=payload.comment,
    )
    return BadgeVoteResponse(**result)
