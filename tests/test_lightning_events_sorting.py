from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

from backend.app.repositories import lightning_events_repo


@pytest.mark.asyncio
async def test_list_events_filters_past_and_sorts_ascending():
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            """
        )
        await db.execute("INSERT INTO users (id, full_name) VALUES (1, 'Test User')")

        now = datetime.now(timezone.utc)
        past = (now - timedelta(days=1)).isoformat()
        future_early = (now + timedelta(days=1)).isoformat()
        future_late = (now + timedelta(days=2)).isoformat()

        await db.execute(
            """
            INSERT INTO events (
                owner_id, created_by_user_id, created_by_role, created_source, club_label, is_club_event,
                title, description, category, city, location, tags, event_type, capacity, starts_at, status, created_at
            ) VALUES (1,1,'member','app',NULL,0,?,?,?,?,?,?,?,6,?,'published',?)
            """,
            ("Past", "desc", "Нетворкинг", "Алматы", "A", "[]", "offline", past, now.isoformat()),
        )
        await db.execute(
            """
            INSERT INTO events (
                owner_id, created_by_user_id, created_by_role, created_source, club_label, is_club_event,
                title, description, category, city, location, tags, event_type, capacity, starts_at, status, created_at
            ) VALUES (1,1,'member','app',NULL,0,?,?,?,?,?,?,?,6,?,'published',?)
            """,
            ("Future 1", "desc", "Нетворкинг", "Алматы", "B", "[]", "offline", future_early, now.isoformat()),
        )
        await db.execute(
            """
            INSERT INTO events (
                owner_id, created_by_user_id, created_by_role, created_source, club_label, is_club_event,
                title, description, category, city, location, tags, event_type, capacity, starts_at, status, created_at
            ) VALUES (1,1,'member','app',NULL,0,?,?,?,?,?,?,?,6,?,'published',?)
            """,
            ("Future 2", "desc", "Нетворкинг", "Алматы", "C", "[]", "offline", future_late, now.isoformat()),
        )
        await db.commit()

        items = await lightning_events_repo.list_events(db, is_club_event=None, limit=50)

        assert len(items) == 2
        assert items[0]["title"] == "Future 1"
        assert items[1]["title"] == "Future 2"
        assert items[0]["starts_at"] <= items[1]["starts_at"]
