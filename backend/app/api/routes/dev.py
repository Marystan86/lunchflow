from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.db import get_db
from backend.app.settings import settings
from backend.app.services import dev_service


router = APIRouter(prefix="/dev")

def _ensure_dev_mode() -> None:
    if settings.env != "dev":
        raise HTTPException(status_code=404, detail="not found")


def _resolve_dev_user_id(request: Request) -> int:
    candidate = request.headers.get("X-Dev-User-Id") or request.query_params.get("dev_user_id")
    if candidate is None or str(candidate).strip() == "":
        return int(settings.dev_auth_user_id)
    try:
        parsed = int(str(candidate).strip())
    except ValueError:
        return int(settings.dev_auth_user_id)
    return max(1, parsed)


@router.get("/users")
async def dev_users(db=Depends(get_db)) -> list[dict]:
    _ensure_dev_mode()
    result = await dev_service.list_dev_users(db)
    await db.commit()
    return result


@router.get("/whoami")
async def dev_whoami(request: Request, db=Depends(get_db)) -> dict:
    _ensure_dev_mode()
    user_id = _resolve_dev_user_id(request)
    user = await dev_service.get_or_create_dev_user(db, int(user_id))
    await db.commit()
    return {
        "id": int(user["id"]),
        "name": str(user["name"]),
        "env": settings.env,
    }
