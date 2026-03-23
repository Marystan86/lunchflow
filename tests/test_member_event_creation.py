import pytest
import aiosqlite

from backend.app.services import events_service
from backend.app.settings import settings


@pytest.mark.asyncio
async def test_create_member_event_registers_creator():
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                role TEXT DEFAULT 'member',
                is_admin INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                full_name TEXT
            );
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                created_by_user_id INTEGER NOT NULL,
                created_by_role TEXT NOT NULL,
                created_source TEXT NOT NULL,
                club_label TEXT,
                is_club_event INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                city TEXT,
                location TEXT,
                tags TEXT,
                event_type TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                starts_at TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                confirmed_at TEXT
            );
            CREATE TABLE event_participants (
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                joined_at TEXT NOT NULL,
                UNIQUE(event_id, user_id)
            );
            CREATE TABLE news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                tag TEXT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                media_urls TEXT,
                entity_type TEXT,
                entity_id INTEGER,
                created_by_user_id INTEGER,
                created_at TEXT NOT NULL,
                is_pinned INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            );
            """
        )
        await db.execute(
            "INSERT INTO users (tg_id, role, is_admin, status, full_name) VALUES (1001, 'member', 0, 'active', 'Test User')"
        )
        await db.commit()

        payload = {
            "title": "Test Group Event",
            "description": "Test description",
            "starts_at": "2099-03-10T19:00:00",
            "event_type": "online",
            "city": None,
            "location": None,
            "capacity": 6,
            "category": "Нетворкинг",
            "tags": ["Нетворкинг"],
        }
        current_user = {"id": 1}
        event = await events_service.create_member_event(db, payload=payload, current_user=current_user)
        await db.commit()

        assert event["id"] > 0
        assert event["is_club_event"] is False
        assert event["created_by_user_id"] == 1
        assert event["created_by_role"] == "member"
        assert event["registered"] == 1

        cur = await db.execute("SELECT COUNT(*) FROM event_participants WHERE event_id = ? AND user_id = 1", (event["id"],))
        row = await cur.fetchone()
        assert int(row[0]) == 1

        news_row = await (await db.execute(
            "SELECT entity_type, entity_id, title FROM news WHERE entity_type='event' AND entity_id = ? LIMIT 1",
            (event["id"],),
        )).fetchone()
        assert news_row is not None
        assert str(news_row[0]) == "event"
        assert int(news_row[1]) == int(event["id"])


@pytest.mark.asyncio
async def test_create_group_event_dev_mode():
    old_env = settings.env
    old_dev_enabled = settings.dev_auth_enabled
    old_dev_user_id = settings.dev_auth_user_id
    object.__setattr__(settings, "env", "dev")
    object.__setattr__(settings, "dev_auth_enabled", True)
    object.__setattr__(settings, "dev_auth_user_id", 1)
    try:
        async with aiosqlite.connect(":memory:") as db:
            db.row_factory = aiosqlite.Row
            await db.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_id INTEGER UNIQUE NOT NULL,
                    role TEXT DEFAULT 'member',
                    is_admin INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    full_name TEXT
                );
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    created_by_user_id INTEGER NOT NULL,
                    created_by_role TEXT NOT NULL,
                    created_source TEXT NOT NULL,
                    club_label TEXT,
                    is_club_event INTEGER NOT NULL DEFAULT 0,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    city TEXT,
                    location TEXT,
                    tags TEXT,
                    event_type TEXT NOT NULL,
                    capacity INTEGER NOT NULL,
                    starts_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    confirmed_at TEXT
                );
                CREATE TABLE event_participants (
                    event_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    joined_at TEXT NOT NULL,
                    UNIQUE(event_id, user_id)
                );
                CREATE TABLE news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    tag TEXT,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    media_urls TEXT,
                    entity_type TEXT,
                    entity_id INTEGER,
                    created_by_user_id INTEGER,
                    created_at TEXT NOT NULL,
                    is_pinned INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                );
                """
            )
            await db.execute(
                "INSERT INTO users (id, tg_id, role, is_admin, status, full_name) VALUES (1, 1001, 'member', 0, 'active', 'Dev User')"
            )
            await db.commit()

            payload = {
                "title": "Dev Group Event",
                "description": "Dev description",
                "starts_at": "2099-03-10T19:00:00.000Z",
                "event_type": "online",
                "city": None,
                "location": None,
                "capacity": 6,
                "category": "Нетворкинг",
                "tags": ["Нетворкинг"],
            }
            event = await events_service.create_member_event(db, payload=payload, current_user={})
            await db.commit()

            assert event["id"] > 0
            assert event["created_by_user_id"] == 1
            assert event["registered"] == 1

            cur = await db.execute(
                "SELECT status FROM event_participants WHERE event_id = ? AND user_id = 1",
                (event["id"],),
            )
            row = await cur.fetchone()
            assert row is not None
            assert str(row[0]) == "registered"

            news_row = await (await db.execute(
                "SELECT entity_type, entity_id FROM news WHERE entity_type='event' AND entity_id = ? LIMIT 1",
                (event["id"],),
            )).fetchone()
            assert news_row is not None
            assert str(news_row[0]) == "event"
            assert int(news_row[1]) == int(event["id"])
    finally:
        object.__setattr__(settings, "env", old_env)
        object.__setattr__(settings, "dev_auth_enabled", old_dev_enabled)
        object.__setattr__(settings, "dev_auth_user_id", old_dev_user_id)
