from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_current_user
from backend.app.models.schemas import MemberDetail, MemberListItem
from backend.app.services import users_service


router = APIRouter(prefix="/members")


@router.get("", response_model=list[MemberListItem])
async def members_list(
    query: str | None = None,
    city: str | None = None,
    tags: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(get_current_user),
) -> list[MemberListItem]:
    rows = await users_service.list_members(
        {
            "query": query,
            "city": city,
            "tags": tags,
            "limit": limit,
            "offset": offset,
        }
    )
    return [MemberListItem(**row) for row in rows]


@router.get("/public", response_model=list[MemberListItem])
async def members_public(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[MemberListItem]:
    rows = await users_service.list_public_members(limit=limit, offset=offset)
    return [MemberListItem(**row) for row in rows]


@router.get("/{member_id}", response_model=MemberDetail)
async def member_detail(member_id: int, current_user: dict = Depends(get_current_user)) -> MemberDetail:
    detail = await users_service.get_member_detail(member_id, current_user)
    return MemberDetail(**detail)
