from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.db import get_db
from backend.app.repositories import users_repo
from backend.app.services.users_service import decode_access_token
from backend.app.settings import settings


bearer_scheme = HTTPBearer(auto_error=False)


def _is_dev_auth_enabled() -> bool:
    return settings.env == "dev" and settings.dev_auth_enabled


def _resolve_dev_user_id(request: Request) -> int:
    candidate = request.headers.get("X-Dev-User-Id") or request.query_params.get("dev_user_id")
    if candidate is None or str(candidate).strip() == "":
        return int(settings.dev_auth_user_id)
    try:
        parsed = int(str(candidate).strip())
    except ValueError:
        return int(settings.dev_auth_user_id)
    return max(1, parsed)


async def _get_or_create_dev_user(db, user_id: int) -> dict:
    user = await users_repo.get_by_id(db, int(user_id))
    if user is not None:
        return user

    tg_id = 980000000 + int(user_id)
    while True:
        existing_tg = await users_repo.get_by_tg_id(db, tg_id)
        if existing_tg is None:
            break
        tg_id += 1

    await db.execute(
        """
        INSERT INTO users (
            id, tg_id, source, tg_username, full_name, role, is_admin, status, created_at, updated_at
        )
        VALUES (?, ?, 'real', ?, ?, 'member', 0, 'active', datetime('now'), datetime('now'))
        """,
        (
            int(user_id),
            int(tg_id),
            f"dev_user_{int(user_id)}",
            f"Dev User {int(user_id)}",
        ),
    )
    await db.commit()
    created = await users_repo.get_by_id(db, int(user_id))
    if created is None:
        raise HTTPException(status_code=500, detail="failed to create dev user")
    return created


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db=Depends(get_db),
) -> dict:
    if _is_dev_auth_enabled():
        if credentials and credentials.scheme.lower() == "bearer":
            user_id = decode_access_token(credentials.credentials)
            user = await users_repo.get_by_id(db, user_id)
            if user is not None:
                return user
        dev_user_id = _resolve_dev_user_id(request)
        return await _get_or_create_dev_user(db, dev_user_id)

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        user_id = decode_access_token(credentials.credentials)
    except HTTPException as exc:
        raise HTTPException(status_code=401, detail="Not authenticated") from exc
    user = await users_repo.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db=Depends(get_db),
) -> dict | None:
    if _is_dev_auth_enabled():
        if credentials and credentials.scheme.lower() == "bearer":
            try:
                user_id = decode_access_token(credentials.credentials)
            except HTTPException:
                user_id = _resolve_dev_user_id(request)
            user = await users_repo.get_by_id(db, int(user_id))
            if user is not None:
                return user
            return await _get_or_create_dev_user(db, int(user_id))
        dev_user_id = _resolve_dev_user_id(request)
        return await _get_or_create_dev_user(db, dev_user_id)

    if not credentials or credentials.scheme.lower() != "bearer":
        return None
    try:
        user_id = decode_access_token(credentials.credentials)
    except HTTPException:
        return None
    user = await users_repo.get_by_id(db, user_id)
    return user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") not in {"admin", "superadmin", "community_admin"} and int(
        current_user.get("is_admin") or 0
    ) != 1:
        raise HTTPException(status_code=403, detail="admin access required")
    return current_user
