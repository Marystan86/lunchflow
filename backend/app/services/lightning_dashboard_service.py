from backend.app.repositories import meeting_requests_repo
from backend.app.services import lightning_event_service


def _request_to_item(row: dict, *, incoming: bool) -> dict:
    title = row.get("counterpart_name") or "Участник"
    subtitle = "Входящий запрос 1-на-1" if incoming else "Запрос на встречу 1-на-1"
    return {
        "id": int(row["id"]),
        "title": title,
        "subtitle": subtitle,
        "status": str(row.get("status") or "pending"),
        "scheduled_for": row.get("scheduled_for"),
        "format": row.get("format"),
        "location": row.get("location"),
        "message": row.get("message"),
    }


def _event_to_item(row: dict, *, is_club_event: bool) -> dict:
    subtitle = "Клубный ивент" if is_club_event else "Групповая встреча"
    created_by_name = row.get("created_by_name")
    created_by_role = row.get("created_by_role")
    if created_by_role == "member" and created_by_name:
        subtitle = f"От участника: {created_by_name}"
    elif created_by_role == "club":
        subtitle = "Клубный ивент"
    return {
        "id": int(row["id"]),
        "title": row.get("title") or "Событие",
        "subtitle": subtitle,
        "status": str(row.get("status") or "published"),
        "scheduled_for": row.get("starts_at"),
        "format": row.get("event_type"),
        "city": row.get("city"),
        "location": row.get("location"),
        "message": row.get("description"),
        "event_id": int(row["id"]),
        "is_club_event": bool(row.get("is_club_event", 0)),
        "registered": int(row.get("registered_count") or 0),
        "capacity": int(row.get("capacity") or 0),
        "category": row.get("category"),
        "created_by_user_id": int(row["created_by_user_id"]) if row.get("created_by_user_id") is not None else None,
        "created_by_role": created_by_role,
        "created_by_name": created_by_name,
        "tags": row.get("tags"),
    }


def event_to_item(row: dict, *, is_club_event: bool) -> dict:
    return _event_to_item(row, is_club_event=is_club_event)


async def build_dashboard(db, *, user_id: int, limit: int = 50) -> dict:
    outgoing = await meeting_requests_repo.list_outgoing(db, int(user_id), int(limit))
    incoming = await meeting_requests_repo.list_incoming(db, int(user_id), int(limit))
    group_events = await lightning_event_service.list_all_events(db, limit=int(limit))
    club_events = await lightning_event_service.list_club_events(db, limit=int(limit))

    return {
        "outgoing_requests": [_request_to_item(row, incoming=False) for row in outgoing],
        "incoming_requests": [_request_to_item(row, incoming=True) for row in incoming],
        "group_meetings": [_event_to_item(row, is_club_event=False) for row in group_events],
        "club_events": [_event_to_item(row, is_club_event=True) for row in club_events],
    }


async def build_public_dashboard(db, *, limit: int = 50) -> dict:
    recent = await meeting_requests_repo.list_recent_requests(db, limit=int(limit))
    outgoing_preview = []
    incoming_preview = []
    for idx, row in enumerate(recent):
        if len(outgoing_preview) < limit:
            outgoing_preview.append(
                {
                    "id": int(row["id"]),
                    "title": row.get("to_user_name") or "Участник",
                    "subtitle": "Запрос на встречу 1-на-1",
                    "status": str(row.get("status") or "pending"),
                    "scheduled_for": row.get("scheduled_for"),
                    "format": row.get("format"),
                    "location": row.get("location"),
                    "message": row.get("message"),
                }
            )
        if len(incoming_preview) < limit:
            incoming_preview.append(
                {
                    "id": int(row["id"]),
                    "title": row.get("from_user_name") or "Участник",
                    "subtitle": "Входящий запрос 1-на-1",
                    "status": str(row.get("status") or "pending"),
                    "scheduled_for": row.get("scheduled_for"),
                    "format": row.get("format"),
                    "location": row.get("location"),
                    "message": row.get("message"),
                }
            )
        if idx >= limit:
            break

    group_events = await lightning_event_service.list_all_events(db, limit=int(limit))
    club_events = await lightning_event_service.list_club_events(db, limit=int(limit))
    return {
        "outgoing_requests": outgoing_preview,
        "incoming_requests": incoming_preview,
        "group_meetings": [_event_to_item(row, is_club_event=False) for row in group_events],
        "club_events": [_event_to_item(row, is_club_event=True) for row in club_events],
    }
