from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_user
from backend.app.models.schemas import MemberDetail, UserMeUpdate
from backend.app.services import users_service


router = APIRouter(prefix="/users")


@router.get("/me", response_model=MemberDetail)
async def get_me(current_user: dict = Depends(get_current_user)) -> MemberDetail:
    return MemberDetail(**(await users_service.get_me(current_user)))


@router.patch("/me", response_model=MemberDetail)
async def patch_me(payload: UserMeUpdate, current_user: dict = Depends(get_current_user)) -> MemberDetail:
    updated = await users_service.update_me(int(current_user["id"]), payload.model_dump(exclude_unset=True))
    return MemberDetail(**updated)
