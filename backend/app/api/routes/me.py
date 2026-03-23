from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_user
from backend.app.models.schemas import MemberDetail
from backend.app.services import users_service


router = APIRouter()


@router.get("/me", response_model=MemberDetail)
async def get_me_alias(current_user: dict = Depends(get_current_user)) -> MemberDetail:
    return MemberDetail(**(await users_service.get_me(current_user)))
