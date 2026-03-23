from fastapi import HTTPException
import json

from backend.app.repositories import lightning_events_repo, users_repo


async def create_user_event(db, *, creator_user_id: int, payload: dict) -> dict:
    creator = await users_repo.get_by_id(db, int(creator_user_id))
    if creator is None:
        raise HTTPException(status_code=404, detail="creator user not found")
    if creator.get("role") in {"admin", "superadmin", "community_admin"} or int(creator.get("is_admin") or 0) == 1:
        raise HTTPException(status_code=400, detail="admin users must create club events")
    tags_json = json.dumps(payload.get("tags") or [], ensure_ascii=False)
    return await lightning_events_repo.create_event(
        db,
        owner_id=int(creator_user_id),
        created_by_user_id=int(creator_user_id),
        created_by_role="member",
        created_source="app",
        club_label=None,
        is_club_event=False,
        title=str(payload["title"]).strip(),
        description=payload.get("description"),
        category=payload.get("category"),
        city=payload.get("city"),
        location=payload.get("location"),
        tags=tags_json,
        event_type=str(payload["event_type"]).strip(),
        capacity=int(payload["capacity"]),
        starts_at=str(payload["starts_at"]),
        status="published",
    )


async def create_club_event(db, *, owner_user_id: int, payload: dict) -> dict:
    creator = await users_repo.get_by_id(db, int(owner_user_id))
    if creator is None:
        raise HTTPException(status_code=404, detail="creator user not found")
    if creator.get("role") not in {"admin", "superadmin", "community_admin"} and int(creator.get("is_admin") or 0) != 1:
        raise HTTPException(status_code=403, detail="club event requires admin creator")

    creator_name = str(creator.get("full_name") or "").strip()
    club_label = f"{creator_name} / Комьюнити-админ" if creator_name else "Клуб 999"
    tags_json = json.dumps(payload.get("tags") or [], ensure_ascii=False)
    return await lightning_events_repo.create_event(
        db,
        owner_id=int(owner_user_id),
        created_by_user_id=int(owner_user_id),
        created_by_role="club",
        created_source="admin",
        club_label=club_label,
        is_club_event=True,
        title=str(payload["title"]).strip(),
        description=payload.get("description"),
        category=payload.get("category"),
        city=payload.get("city"),
        location=payload.get("location"),
        tags=tags_json,
        event_type=str(payload["event_type"]).strip(),
        capacity=int(payload["capacity"]),
        starts_at=str(payload["starts_at"]),
        status="published",
    )


async def join_event(db, *, event_id: int, user_id: int) -> dict:
    event = await lightning_events_repo.get_event_by_id(db, int(event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    capacity = int(event.get("capacity") or 0)
    registered_count = await lightning_events_repo.count_registered(db, int(event_id))
    if capacity > 0 and registered_count >= capacity:
        raise HTTPException(status_code=409, detail="event capacity reached")
    await lightning_events_repo.set_participant_status(
        db,
        event_id=int(event_id),
        user_id=int(user_id),
        status="registered",
    )
    return {"event_id": int(event_id), "user_id": int(user_id), "status": "registered"}


async def leave_event(db, *, event_id: int, user_id: int) -> dict:
    event = await lightning_events_repo.get_event_by_id(db, int(event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    await lightning_events_repo.set_participant_status(
        db,
        event_id=int(event_id),
        user_id=int(user_id),
        status="cancelled",
    )
    return {"event_id": int(event_id), "user_id": int(user_id), "status": "cancelled"}


async def list_group_events(db, *, limit: int = 50) -> list[dict]:
    return await lightning_events_repo.list_events(db, is_club_event=False, limit=int(limit))


async def list_club_events(db, *, limit: int = 50) -> list[dict]:
    return await lightning_events_repo.list_events(db, is_club_event=True, limit=int(limit))


async def list_all_events(db, *, limit: int = 50) -> list[dict]:
    return await lightning_events_repo.list_events(db, is_club_event=None, limit=int(limit))
