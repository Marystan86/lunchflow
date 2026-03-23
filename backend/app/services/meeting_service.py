from fastapi import HTTPException

from backend.app.repositories import meetings_repo


VALID_MEETING_STATUSES = {"scheduled", "completed", "no_show", "disputed", "cancelled"}


def _is_participant(meeting: dict, user_id: int) -> bool:
    candidates = {
        meeting.get("participant_a_id"),
        meeting.get("participant_b_id"),
        meeting.get("initiator_id"),
        meeting.get("receiver_id"),
    }
    return int(user_id) in {int(v) for v in candidates if v is not None}


async def get_meeting_for_user(db, *, meeting_id: int, user_id: int) -> dict:
    meeting = await meetings_repo.get_by_id(db, int(meeting_id))
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    if not _is_participant(meeting, int(user_id)):
        raise HTTPException(status_code=403, detail="forbidden")
    return meeting


async def set_meeting_status(db, *, meeting_id: int, user_id: int, status: str) -> dict:
    if status not in VALID_MEETING_STATUSES:
        raise HTTPException(status_code=400, detail="invalid meeting status")
    meeting = await get_meeting_for_user(db, meeting_id=int(meeting_id), user_id=int(user_id))
    _ = meeting
    updated = await meetings_repo.set_status(db, int(meeting_id), status=status)
    if updated is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return updated


async def list_user_meetings(db, *, user_id: int, limit: int = 100) -> list[dict]:
    return await meetings_repo.list_user_meetings(db, int(user_id), int(limit))
