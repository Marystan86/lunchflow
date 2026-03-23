import asyncio
import random
from datetime import datetime, timedelta

import aiosqlite
from fastapi import HTTPException

from backend.app.db import init_db
from backend.app.models.schemas import NewsCreateRequest
from backend.app.repositories import badges_repo, demo_seed_repo
from backend.app.services import badges_service, news_service, points_service
from backend.app.settings import settings


SAMPLE_PROFILES = [
    ("Aidar Bekov", "aidar_bekov", "TechGrow", "SaaS"),
    ("Alina Seitova", "alina_seitova", "ScaleHub", "Consulting"),
    ("Nursultan Ibraev", "nurs_ibraev", "DataWay", "AI"),
    ("Mariya Kasenova", "maria_kasenova", "RetailFlow", "Retail"),
    ("Erlan Tursynov", "erlan_tursynov", "FinBridge", "FinTech"),
    ("Dana Zhumabayeva", "dana_zh", "HR Pulse", "HR"),
    ("Ilyas Nurgaliev", "ilyas_nur", "NoCode Lab", "No-code"),
    ("Sofiya Karimova", "sofia_karimova", "Brand Art", "Marketing"),
    ("Roman Abdrakhmanov", "roman_abd", "Legal Point", "Legal"),
    ("Vera Akhmetova", "vera_ahmetova", "Wellness Core", "Wellness"),
    ("Timur Smagulov", "timur_smag", "CloudFrame", "Cloud"),
    ("Madina Ermekova", "madina_ermek", "EdSmart", "EdTech"),
    ("Arsen Kozhakhmet", "arsen_kozh", "DevStudio", "Software"),
    ("Elena Rakhimova", "elena_rah", "Growth DNA", "Growth"),
    ("Kuat Ospanov", "kuat_osp", "LogiTrack", "Logistics"),
    ("Kira Zhakupova", "kira_zhak", "Design Peak", "Design"),
    ("Leonid Kravtsov", "leonid_krav", "Ops Mind", "Operations"),
    ("Nadezhda Sadykova", "nadezhda_sad", "MedLine", "Health"),
    ("Ayan Kenzhebaev", "ayan_kenzh", "Mobility X", "Mobility"),
    ("Aigerim Nurlanova", "aigerim_nur", "Content Forge", "Media"),
]

PEER_CODES = ["pleasant_talker", "expert", "helpful", "useful_contact", "fast_agreement"]
ADMIN_NEWS_TAGS = ["\u041a\u043b\u0443\u0431", "\u041e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0435", "\u0410\u043d\u043e\u043d\u0441", "\u0412\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0441\u0442\u044c"]
EVENT_ANNOUNCEMENT_TAGS = ["\u0410\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c", "\u041c\u0430\u0441\u0442\u0435\u0440\u043c\u0430\u0439\u043d\u0434", "\u0414\u0435\u043d\u044c 999", "\u041d\u0435\u0442\u0432\u043e\u0440\u043a\u0438\u043d\u0433"]
EVENT_SUMMARY_TAGS = ["\u0418\u0442\u043e\u0433\u0438", "\u041e\u0442\u0447\u0435\u0442", "\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u044b"]
EVENT_CATEGORIES = [
    "\u041d\u0435\u0442\u0432\u043e\u0440\u043a\u0438\u043d\u0433",
    "\u041c\u0430\u0441\u0442\u0435\u0440\u043c\u0430\u0439\u043d\u0434",
    "\u0410\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c",
    "\u0414\u0435\u043d\u044c 999",
    "\u0418\u043d\u0432\u0435\u0441\u0442\u043e\u0440\u044b",
    "\u041f\u0440\u043e\u0434\u0443\u043a\u0442",
]


def _iso_days_ago(days_ago: int, hour: int = 12) -> str:
    dt = datetime.utcnow() - timedelta(days=days_ago)
    dt = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    return dt.isoformat()


async def _seed_badges_catalog(db: aiosqlite.Connection) -> None:
    for badge in badges_repo.SYSTEM_SEED_BADGES:
        await badges_repo.upsert_badge(db, badge)
    for badge in badges_repo.PEER_SEED_BADGES:
        await badges_repo.upsert_badge(db, badge)


def _build_balanced_pairs(user_ids: list[int], meetings_count: int, rnd: random.Random) -> list[tuple[int, int]]:
    pair_counts = {(min(a, b), max(a, b)): 0 for idx, a in enumerate(user_ids) for b in user_ids[idx + 1 :]}
    user_load = {uid: 0 for uid in user_ids}
    pairs: list[tuple[int, int]] = []
    for _ in range(meetings_count):
        sorted_users = sorted(user_ids, key=lambda uid: (user_load[uid], rnd.random()))
        a = sorted_users[0]
        candidates = [uid for uid in sorted_users[1:] if uid != a]
        candidates.sort(key=lambda uid: (pair_counts[(min(a, uid), max(a, uid))], user_load[uid], rnd.random()))
        b = candidates[0]
        pair_counts[(min(a, b), max(a, b))] += 1
        user_load[a] += 1
        user_load[b] += 1
        pairs.append((a, b))
    return pairs


async def _seed_peer_votes_with_db(
    db: aiosqlite.Connection,
    sample_user_ids: list[int],
    meetings_by_user: dict[int, list[dict]],
) -> int:
    votes_created = 0
    targets = sample_user_ids[: min(8, len(sample_user_ids))]

    for idx, target_user in enumerate(targets):
        badge_code = PEER_CODES[idx % len(PEER_CODES)]
        voters_used: set[int] = set()
        for meeting in meetings_by_user.get(target_user, []):
            other = int(meeting["receiver_id"] if int(meeting["initiator_id"]) == target_user else meeting["initiator_id"])
            if other == target_user or other in voters_used:
                continue
            try:
                await badges_service.vote_badge_with_db(
                    db=db,
                    from_user_id=other,
                    to_user_id=target_user,
                    badge_code=badge_code,
                    meeting_id=int(meeting["id"]),
                    comment="РћС‚Р»РёС‡РЅР°СЏ РІСЃС‚СЂРµС‡Р°, Р±С‹Р»Рѕ РїРѕР»РµР·РЅРѕ",
                )
                votes_created += 1
                voters_used.add(other)
            except HTTPException:
                continue
            if len(voters_used) >= 3:
                break
    return votes_created


async def seed_demo_ecosystem(clear_sample_data: bool = True) -> dict:
    await init_db()
    await badges_service.ensure_seed()
    rnd = random.Random(42)
    stats = {
        "users_created": 0,
        "meetings_created": 0,
        "events_created": 0,
        "points_transactions_created": 0,
        "badge_votes_created": 0,
        "user_badges_granted": 0,
        "news_created": 0,
        "sample_cleanup": {},
    }

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row

        if clear_sample_data:
            stats["sample_cleanup"] = await demo_seed_repo.cleanup_sample_data(db)

        await _seed_badges_catalog(db)
        community_admin_id = await demo_seed_repo.ensure_community_admin_user(db)

        sample_users: list[dict] = []
        for idx, (full_name, username, company_name, industry) in enumerate(SAMPLE_PROFILES, start=1):
            user_id = await demo_seed_repo.create_sample_user(
                db,
                tg_id=900000000 + idx,
                full_name=full_name,
                tg_username=username,
                role="admin" if idx == 1 else "member",
                source="sample",
                status="active",
                company_name=company_name,
                industry=industry,
                annual_revenue=f"{(idx % 8) + 1}0-{(idx % 8) + 2}0 \u043c\u043b\u043d \u20b8",
                employee_count=5 + idx,
                core_competencies="\u041f\u0440\u043e\u0434\u0430\u0436\u0438, \u0440\u0430\u0437\u0432\u0438\u0442\u0438\u0435 \u043f\u0440\u043e\u0434\u0443\u043a\u0442\u0430, \u043f\u0430\u0440\u0442\u043d\u0435\u0440\u0441\u0442\u0432\u0430",
                goal_2025="\u0412\u044b\u0439\u0442\u0438 \u043d\u0430 \u043d\u043e\u0432\u044b\u0439 \u0440\u044b\u043d\u043e\u043a \u0438 \u0443\u0441\u0438\u043b\u0438\u0442\u044c \u043a\u043e\u043c\u0430\u043d\u0434\u0443 \u043a 2025",
                club_request="\u0418\u0449\u0443 \u0440\u0435\u043b\u0435\u0432\u0430\u043d\u0442\u043d\u044b\u0435 \u0437\u043d\u0430\u043a\u043e\u043c\u0441\u0442\u0432\u0430 \u0438 \u043f\u0430\u0440\u0442\u043d\u0435\u0440\u043e\u0432 \u0432 \u043a\u043b\u0443\u0431\u0435",
                hobbies="\u041f\u0443\u0442\u0435\u0448\u0435\u0441\u0442\u0432\u0438\u044f, \u0441\u043f\u043e\u0440\u0442, \u043a\u043d\u0438\u0433\u0438",
                help_offer="\u041f\u043e\u043c\u043e\u0433\u0443 \u0441 growth-\u0441\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u0435\u0439 \u0438 \u043d\u0435\u0442\u0432\u043e\u0440\u043a\u0438\u043d\u0433\u043e\u043c",
            )
            sample_users.append({"id": user_id, "full_name": full_name, "role": "admin" if idx == 1 else "member"})
        await db.commit()
        stats["users_created"] = len(sample_users)

        sample_user_ids = [int(u["id"]) for u in sample_users]
        pairs = _build_balanced_pairs(sample_user_ids, 60, rnd)
        for i, (initiator_id, receiver_id) in enumerate(pairs, start=1):
            await demo_seed_repo.create_confirmed_meeting(
                db,
                initiator_id=initiator_id,
                receiver_id=receiver_id,
                created_at=_iso_days_ago(days_ago=100 - i, hour=9 + (i % 8)),
            )
        await db.commit()
        stats["meetings_created"] = len(pairs)

        event_specs = [
            (
                "\u0411\u0438\u0437\u043d\u0435\u0441-\u0437\u0430\u0432\u0442\u0440\u0430\u043a \u043e\u0441\u043d\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439",
                "\u041e\u0431\u0441\u0443\u0434\u0438\u043c \u043a\u0435\u0439\u0441\u044b \u0440\u043e\u0441\u0442\u0430, \u043a\u0430\u043d\u0430\u043b\u044b \u043f\u0440\u043e\u0434\u0430\u0436 \u0438 \u043f\u0430\u0440\u0442\u043d\u0435\u0440\u0441\u0442\u0432\u0430.",
                "offline",
                20,
                20,
                sample_user_ids[0],
                "\u041d\u0435\u0442\u0432\u043e\u0440\u043a\u0438\u043d\u0433",
            ),
            (
                "GTM Sprint",
                "\u0420\u0430\u0437\u0431\u0435\u0440\u0435\u043c \u043f\u043e\u0437\u0438\u0446\u0438\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435, \u0432\u043e\u0440\u043e\u043d\u043a\u0443 \u0438 \u043f\u0435\u0440\u0432\u044b\u0435 \u043f\u0440\u043e\u0434\u0430\u0436\u0438.",
                "online",
                30,
                14,
                sample_user_ids[1],
                "\u041f\u0440\u043e\u0434\u0443\u043a\u0442",
            ),
            (
                "Product Clinic",
                "\u041f\u0440\u043e\u0439\u0434\u0435\u043c\u0441\u044f \u043f\u043e unit-\u044d\u043a\u043e\u043d\u043e\u043c\u0438\u043a\u0435, retention \u0438 roadmap \u043a\u043e\u043c\u0430\u043d\u0434.",
                "offline",
                18,
                10,
                sample_user_ids[0],
                "\u041c\u0430\u0441\u0442\u0435\u0440\u043c\u0430\u0439\u043d\u0434",
            ),
            (
                "Investor AMA",
                "\u041e\u0442\u043a\u0440\u044b\u0442\u0430\u044f Q&A-\u0441\u0435\u0441\u0441\u0438\u044f \u0441 \u0438\u043d\u0432\u0435\u0441\u0442\u043e\u0440\u0430\u043c\u0438 \u0438 \u0444\u0430\u0443\u043d\u0434\u0435\u0440\u0430\u043c\u0438.",
                "online",
                25,
                5,
                sample_user_ids[2],
                "\u0418\u043d\u0432\u0435\u0441\u0442\u043e\u0440\u044b",
            ),
        ]

        events_seed_rows: list[dict] = []
        event_ids: list[int] = []
        for title, description, event_type, capacity, days_ago, owner_id, category in event_specs:
            starts_at = _iso_days_ago(days_ago=days_ago, hour=18)
            creator_role = "club" if int(owner_id) == int(community_admin_id) else "member"
            event_id = await demo_seed_repo.create_event(
                db,
                owner_id=owner_id,
                created_by_user_id=int(owner_id),
                created_by_role=creator_role,
                created_source="seed",
                club_label="Клуб 999" if creator_role == "club" else None,
                is_club_event=1 if creator_role == "club" else 0,
                title=title,
                description=description,
                category=category,
                event_type=event_type,
                capacity=capacity,
                starts_at=starts_at,
                status="confirmed",
            )
            event_ids.append(event_id)
            events_seed_rows.append(
                {
                    "id": int(event_id),
                    "title": title,
                    "description": description,
                    "category": category,
                    "starts_at": starts_at,
                }
            )
            participants = rnd.sample(sample_user_ids, k=rnd.randint(5, 10))
            if owner_id not in participants:
                participants.append(owner_id)
            for user_id in participants:
                await demo_seed_repo.add_event_participant(
                    db,
                    event_id=event_id,
                    user_id=int(user_id),
                    status="attended",
                    joined_at=starts_at,
                )

        # March origin seed: 2 club events + 1 member event.
        march_specs = [
            (
                "Клубный стратегический круг",
                "Мартовская стратегическая встреча клуба с фокусом на партнерства и рост.",
                "offline",
                30,
                datetime(datetime.utcnow().year, 3, 10, 19, 0).isoformat(),
                int(community_admin_id),
                "Нетворкинг",
                "club",
            ),
            (
                "Club 999 Mastermind",
                "Комьюнити-админ модерирует мастермайнд по масштабированию и найму.",
                "online",
                40,
                datetime(datetime.utcnow().year, 3, 18, 18, 30).isoformat(),
                int(community_admin_id),
                "Мастермайнд",
                "club",
            ),
            (
                "Member Growth Session",
                "Участник клуба делится практикой воронки и операционного контроля.",
                "online",
                24,
                datetime(datetime.utcnow().year, 3, 24, 19, 0).isoformat(),
                int(sample_user_ids[3]),
                "Продукт",
                "member",
            ),
        ]
        for title, description, event_type, capacity, starts_at, owner_id, category, creator_role in march_specs:
            event_id = await demo_seed_repo.create_event(
                db,
                owner_id=int(owner_id),
                created_by_user_id=int(owner_id),
                created_by_role=creator_role,
                created_source="seed",
                club_label="Клуб 999" if creator_role == "club" else None,
                is_club_event=1 if creator_role == "club" else 0,
                title=title,
                description=description,
                category=category,
                event_type=event_type,
                capacity=capacity,
                starts_at=starts_at,
                status="confirmed",
            )
            event_ids.append(event_id)
            events_seed_rows.append(
                {
                    "id": int(event_id),
                    "title": title,
                    "description": description,
                    "category": category,
                    "starts_at": starts_at,
                }
            )
            participants = rnd.sample(sample_user_ids, k=min(len(sample_user_ids), rnd.randint(5, 10)))
            for user_id in participants:
                await demo_seed_repo.add_event_participant(
                    db,
                    event_id=event_id,
                    user_id=int(user_id),
                    status="attended",
                    joined_at=starts_at,
                )
        await db.commit()
        stats["events_created"] = len(event_ids)

        points_created = 0
        for user_id in sample_user_ids:
            await points_service.add_points(
                db,
                user_id=user_id,
                amount=100,
                reason_type="welcome",
                meta={"source": "sample"},
            )
            points_created += 1

        cur = await db.execute("SELECT id, initiator_id, receiver_id FROM meetings WHERE LOWER(status) = 'confirmed'")
        meetings = [dict(r) for r in await cur.fetchall()]
        for meeting in meetings:
            for user_id in (int(meeting["initiator_id"]), int(meeting["receiver_id"])):
                await points_service.add_points(
                    db,
                    user_id=user_id,
                    amount=20,
                    reason_type="meeting_confirmed",
                    entity_type="meeting",
                    entity_id=int(meeting["id"]),
                    meta={"source": "sample"},
                )
                points_created += 1

        cur = await db.execute("SELECT id, owner_id FROM events WHERE LOWER(status) = 'confirmed'")
        events_rows = [dict(r) for r in await cur.fetchall()]
        for event in events_rows:
            await points_service.add_points(
                db,
                user_id=int(event["owner_id"]),
                amount=30,
                reason_type="event_hosted",
                entity_type="event",
                entity_id=int(event["id"]),
                meta={"source": "sample"},
            )
            points_created += 1
            p_cur = await db.execute(
                "SELECT user_id FROM event_participants WHERE event_id = ? AND LOWER(status) = 'attended'",
                (int(event["id"]),),
            )
            for row in await p_cur.fetchall():
                await points_service.add_points(
                    db,
                    user_id=int(row["user_id"]),
                    amount=10,
                    reason_type="event_attended",
                    entity_type="event",
                    entity_id=int(event["id"]),
                    meta={"source": "sample"},
                )
                points_created += 1
        stats["points_transactions_created"] = points_created

        meetings_by_user: dict[int, list[dict]] = {}
        for user_id in sample_user_ids:
            meetings_by_user[user_id] = await demo_seed_repo.list_meetings_for_user(db, user_id)

        stats["badge_votes_created"] = await _seed_peer_votes_with_db(db, sample_user_ids, meetings_by_user)
        print(f"[demo-seed] votes_created={stats['badge_votes_created']}")

        for user_id in sample_user_ids:
            await badges_service.evaluate_system_badges(db, user_id)
        await db.commit()

        cur = await db.execute(
            """
            SELECT COUNT(*)
            FROM user_badges ub
            JOIN users u ON u.id = ub.user_id
            WHERE u.source = 'sample'
            """
        )
        stats["user_badges_granted"] = int((await cur.fetchone())[0])
        print(f"[demo-seed] badges_granted={stats['user_badges_granted']}")

        admin_user = sample_users[0]
        news_created = 0
        used_news_timestamps: set[str] = set()

        def _unique_news_ts(base_dt: datetime, minute_shift: int) -> str:
            ts = base_dt + timedelta(minutes=minute_shift)
            while ts.isoformat() in used_news_timestamps:
                ts = ts + timedelta(minutes=1)
            iso = ts.isoformat()
            used_news_timestamps.add(iso)
            return iso

        for idx, event in enumerate(events_seed_rows):
            starts_dt = datetime.fromisoformat(event["starts_at"])
            announcement_dt = starts_dt - timedelta(days=rnd.randint(5, 10), hours=rnd.randint(1, 6))
            summary_dt = starts_dt + timedelta(days=rnd.randint(1, 2), hours=rnd.randint(2, 8))
            announcement_ts = _unique_news_ts(announcement_dt, idx * 3)
            summary_ts = _unique_news_ts(summary_dt, idx * 3 + 1)

            await news_service.create_event_announcement(
                db,
                event_id=int(event["id"]),
                title=f"\u0410\u043d\u043e\u043d\u0441: {event['title']}",
                body=(
                    f"\u041c\u044b \u0433\u043e\u0442\u043e\u0432\u0438\u043c \u0441\u043e\u0431\u044b\u0442\u0438\u0435 \u00ab{event['title']}\u00bb. "
                    "\u0411\u0443\u0434\u0435\u0442 \u043f\u0440\u0430\u043a\u0442\u0438\u043a\u0430, \u0437\u043d\u0430\u043a\u043e\u043c\u0441\u0442\u0432\u0430 \u0438 \u0440\u0430\u0431\u043e\u0442\u0430 \u043d\u0430\u0434 \u0440\u0435\u0430\u043b\u044c\u043d\u044b\u043c\u0438 \u0437\u0430\u043f\u0440\u043e\u0441\u0430\u043c\u0438. "
                    "\u041f\u0440\u0438\u0441\u043e\u0435\u0434\u0438\u043d\u044f\u0439\u0442\u0435\u0441\u044c \u0438 \u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u043e\u043b\u044c\u0437\u0443 \u0434\u043b\u044f \u0431\u0438\u0437\u043d\u0435\u0441\u0430."
                ),
                tag=str(event["category"] or rnd.choice(EVENT_ANNOUNCEMENT_TAGS)),
                created_at=announcement_ts,
                media_urls=[],
            )
            news_created += 1

            await news_service.create_event_summary(
                db,
                event_id=int(event["id"]),
                title=f"\u0418\u0442\u043e\u0433\u0438: {event['title']}",
                body=(
                    f"\u0412\u0441\u0442\u0440\u0435\u0447\u0430 \u00ab{event['title']}\u00bb \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430. "
                    "\u0423\u0447\u0430\u0441\u0442\u043d\u0438\u043a\u0438 \u043e\u0431\u043c\u0435\u043d\u044f\u043b\u0438\u0441\u044c \u043a\u0435\u0439\u0441\u0430\u043c\u0438, \u0434\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u043b\u0438\u0441\u044c \u043e \u043f\u0430\u0440\u0442\u043d\u0451\u0440\u0441\u0442\u0432\u0430\u0445 \u0438 \u043d\u0430\u043c\u0435\u0442\u0438\u043b\u0438 \u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0435 \u0448\u0430\u0433\u0438. "
                    "\u0421\u043f\u0430\u0441\u0438\u0431\u043e \u0432\u0441\u0435\u043c \u0437\u0430 \u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c."
                ),
                tag="\u0418\u0442\u043e\u0433\u0438",
                created_at=summary_ts,
                media_urls=[],
            )
            news_created += 1

        admin_dates = [
            datetime.utcnow() - timedelta(days=11, hours=2),
            datetime.utcnow() - timedelta(days=3, hours=4),
        ]
        for idx, base_date in enumerate(admin_dates):
            created_at = _unique_news_ts(base_date, idx * 7)
            await news_service.create_admin_post(
                db,
                admin_user={"id": int(admin_user["id"])},
                payload=NewsCreateRequest(
                    title=f"\u041e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0435 \u043a\u043b\u0443\u0431\u0430 #{idx + 1}",
                    body=(
                        "\u0412 \u044d\u0442\u0443 \u043d\u0435\u0434\u0435\u043b\u044e \u043c\u044b \u0441\u043e\u0431\u0440\u0430\u043b\u0438 \u043d\u043e\u0432\u0443\u044e \u0441\u0435\u0440\u0438\u044e \u0432\u0441\u0442\u0440\u0435\u0447. "
                        "\u041f\u0440\u0438\u0441\u044b\u043b\u0430\u0439\u0442\u0435 \u0442\u0435\u043c\u044b, \u043a\u0435\u0439\u0441\u044b \u0438 \u0437\u0430\u043f\u0440\u043e\u0441\u044b \u0434\u043b\u044f \u0440\u0430\u0437\u0431\u043e\u0440\u0430. "
                        "\u0418\u043d\u0442\u0435\u0440\u0435\u0441\u043d\u044b\u0435 \u0438\u0434\u0435\u0438 \u0432\u043a\u043b\u044e\u0447\u0438\u043c \u0432 \u043a\u0430\u043b\u0435\u043d\u0434\u0430\u0440\u044c \u043a\u043b\u0443\u0431\u0430."
                    ),
                    tag=rnd.choice(["\u041a\u043b\u0443\u0431", "\u041e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0435", "\u0410\u043d\u043e\u043d\u0441"]),
                    created_at=created_at,
                    media_urls=[],
                    is_pinned=idx == 0,
                ),
            )
            news_created += 1
        stats["news_created"] = news_created

    return stats


def run_seed(clear_sample_data: bool = True) -> dict:
    return asyncio.run(seed_demo_ecosystem(clear_sample_data=clear_sample_data))

