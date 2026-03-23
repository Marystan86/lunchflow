from fastapi import APIRouter

from backend.app.models.schemas import AuthResponse, TelegramAuthRequest
from backend.app.services import users_service


router = APIRouter(prefix="/auth")


@router.post("/telegram", response_model=AuthResponse)
async def auth_telegram(payload: TelegramAuthRequest) -> AuthResponse:
    user, token = await users_service.auth_with_telegram(payload.initData)
    return AuthResponse(token=token, user=user)
