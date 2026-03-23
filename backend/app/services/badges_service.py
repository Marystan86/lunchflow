from datetime import datetime

from fastapi import HTTPException

from backend.app.db import get_db
from backend.app.repositories import badges_repo
from backend.app.repositories import users_repo


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


async def ensure_seed() -> None:
    async for db in get_db():
        for badge in badges_repo.SYSTEM_SEED_BADGES:
            await badges_repo.upsert_badge(db, badge)
        for badge in badges_repo.PEER_SEED_BADGES:
            await badges_repo.upsert_badge(db, badge)
        await db.commit()
        return


async def _grant_system_badges_for_user(db, user_id: int) -> None:
    catalog = await badges_repo.list_badges(db)
    now_iso = _utc_iso()
    for badge in catalog:
        if badge.get("badge_type") != "system":
            continue
        if badge.get("grant_mode") != "auto":
            continue

        required = int(badge.get("criteria_value") or 0)
        if required <= 0:
            continue

        metric_value = await badges_repo.get_metric_value(db, user_id, badge.get("criteria_type"))
        if metric_value < required:
            continue

        already_has = await badges_repo.user_has_badge(db, int(user_id), int(badge["id"]))
        if not already_has:
            await badges_repo.grant_user_badge(db, int(user_id), int(badge["id"]), now_iso)


async def evaluate_system_badges(db, user_id: int) -> None:
    await _grant_system_badges_for_user(db, int(user_id))


async def vote_badge(
    from_user_id: int,
    to_user_id: int,
    badge_code: str,
    meeting_id: int,
    comment: str | None = None,
) -> dict:
    async for db in get_db():
        result = await vote_badge_with_db(
            db=db,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            badge_code=badge_code,
            meeting_id=meeting_id,
            comment=comment,
        )
        await db.commit()
        return result
    raise HTTPException(status_code=500, detail="database error")


async def vote_badge_with_db(
    db,
    from_user_id: int,
    to_user_id: int,
    badge_code: str,
    meeting_id: int,
    comment: str | None = None,
) -> dict:
    if from_user_id == to_user_id:
        raise HTTPException(status_code=400, detail="you cannot vote for yourself")
    from_user = await users_repo.get_by_id(db, int(from_user_id))
    if from_user is None:
        raise HTTPException(status_code=404, detail="voter user not found")

    to_user = await users_repo.get_by_id(db, int(to_user_id))
    if to_user is None:
        raise HTTPException(status_code=404, detail="target user not found")

    badge = await badges_repo.get_badge_by_code(db, badge_code)
    if badge is None or int(badge.get("is_active", 0)) != 1:
        raise HTTPException(status_code=404, detail="badge not found")
    if badge.get("badge_type") != "peer" or badge.get("grant_mode") != "vote":
        raise HTTPException(status_code=400, detail="badge is not available for peer voting")

    meeting_ok = await badges_repo.is_confirmed_meeting_for_users(db, meeting_id, from_user_id, to_user_id)
    if not meeting_ok:
        raise HTTPException(status_code=404, detail="confirmed meeting not found for both users")

    cooldown_days = int(badge.get("cooldown_days") or 30)
    on_cooldown = await badges_repo.check_cooldown(
        db,
        badge_id=int(badge["id"]),
        from_user_id=int(from_user_id),
        to_user_id=int(to_user_id),
        cooldown_days=cooldown_days,
    )
    if on_cooldown:
        raise HTTPException(status_code=400, detail="cooldown is active for this vote")

    inserted = await badges_repo.insert_vote(
        db,
        badge_id=int(badge["id"]),
        from_user_id=int(from_user_id),
        to_user_id=int(to_user_id),
        meeting_id=int(meeting_id),
        comment=(comment or None),
        created_at=_utc_iso(),
    )
    if not inserted:
        raise HTTPException(status_code=400, detail="vote already exists for this meeting")

    votes_count = await badges_repo.count_unique_votes(db, int(badge["id"]), int(to_user_id))
    threshold = int(badge.get("vote_threshold") or 0)

    granted = False
    has_badge = await badges_repo.user_has_badge(db, int(to_user_id), int(badge["id"]))
    if threshold > 0 and votes_count >= threshold and not has_badge:
        granted = await badges_repo.grant_user_badge(db, int(to_user_id), int(badge["id"]), _utc_iso())

    return {
        "voted": True,
        "votes_count": votes_count,
        "threshold": threshold,
        "granted": bool(granted),
    }


async def get_catalog() -> list[dict]:
    async for db in get_db():
        rows = await badges_repo.list_badges(db)
        return rows
    raise HTTPException(status_code=500, detail="database error")


async def get_my_badges(user_id: int) -> list[dict]:
    async for db in get_db():
        await evaluate_system_badges(db, int(user_id))
        rows = await badges_repo.list_user_badges(db, int(user_id))
        await db.commit()
        return rows
    raise HTTPException(status_code=500, detail="database error")
