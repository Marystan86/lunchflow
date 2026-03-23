from fastapi import HTTPException

from backend.app.repositories import meeting_confirmations_repo, meetings_repo, points_repo
from backend.app.services import points_service


def _participants(meeting: dict) -> tuple[int, int]:
    a = meeting.get("participant_a_id") or meeting.get("initiator_id")
    b = meeting.get("participant_b_id") or meeting.get("receiver_id")
    return int(a), int(b)


async def create_confirmation(
    db,
    *,
    meeting_id: int,
    user_id: int,
    confirmation_status: str,
    comment: str | None = None,
) -> dict:
    if confirmation_status not in {"met", "not_met"}:
        raise HTTPException(status_code=400, detail="invalid confirmation status")

    meeting = await meetings_repo.get_by_id(db, int(meeting_id))
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")

    participant_a, participant_b = _participants(meeting)
    if int(user_id) not in {participant_a, participant_b}:
        raise HTTPException(status_code=403, detail="only meeting participants can confirm")

    inserted = await meeting_confirmations_repo.create_confirmation(
        db,
        meeting_id=int(meeting_id),
        user_id=int(user_id),
        confirmation_status=confirmation_status,
        comment=comment,
    )
    if not inserted:
        raise HTTPException(status_code=400, detail="confirmation already exists for user and meeting")

    confirmations = await meeting_confirmations_repo.list_for_meeting(db, int(meeting_id))
    met_by = {int(row["user_id"]) for row in confirmations if row.get("confirmation_status") == "met"}
    awarded = False
    if participant_a in met_by and participant_b in met_by:
        for uid in (participant_a, participant_b):
            exists = await points_repo.has_ledger_entry(
                db,
                user_id=uid,
                reason_type="meeting_confirmed",
                entity_type="meeting",
                entity_id=int(meeting_id),
            )
            if exists:
                continue
            await points_service.add_points(
                db,
                user_id=uid,
                amount=20,
                reason_type="meeting_confirmed",
                entity_type="meeting",
                entity_id=int(meeting_id),
                meta={"source": "meeting_confirmation"},
            )
            awarded = True

        await meetings_repo.set_status(db, int(meeting_id), status="completed")

    return {
        "meeting_id": int(meeting_id),
        "user_id": int(user_id),
        "confirmation_status": confirmation_status,
        "awarded_points": awarded,
    }
