import aiosqlite

from backend.app.repositories import users_repo


DEV_USERS_CATALOG: list[tuple[int, str]] = [
    (1, "Maydan"),
    (2, "Erlan Tursynov"),
    (3, "Alina Seitova"),
    (4, "Vera Akhmetova"),
    (5, "Arsen Kozhakhmet"),
]


async def list_dev_users(db: aiosqlite.Connection) -> list[dict]:
    result: list[dict] = []
    for user_id, fallback_name in DEV_USERS_CATALOG:
        user = await users_repo.ensure_dev_user(db, user_id=int(user_id), full_name=fallback_name)
        result.append(
            {
                "id": int(user["id"]),
                "name": str(user.get("full_name") or fallback_name),
            }
        )
    return result


async def get_or_create_dev_user(db: aiosqlite.Connection, user_id: int) -> dict:
    default_name = next((name for uid, name in DEV_USERS_CATALOG if int(uid) == int(user_id)), f"Dev User {int(user_id)}")
    user = await users_repo.ensure_dev_user(db, user_id=int(user_id), full_name=default_name)
    return {
        "id": int(user["id"]),
        "name": str(user.get("full_name") or default_name),
    }
