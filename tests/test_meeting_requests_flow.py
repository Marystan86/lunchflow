import pytest
import aiosqlite

from backend.app.repositories import meeting_requests_repo
from backend.app.services import meeting_request_service


@pytest.mark.asyncio
async def test_cross_invites_and_statuses() -> None:
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                full_name TEXT
            );
            CREATE TABLE meeting_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                scheduled_for TEXT,
                format TEXT,
                location TEXT,
                message TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                expires_at TEXT,
                responder_user_id INTEGER,
                responded_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                initiator_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                request_id INTEGER UNIQUE,
                participant_a_id INTEGER,
                participant_b_id INTEGER,
                scheduled_for TEXT,
                format TEXT,
                location TEXT,
                notes TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                confirmed_at TEXT,
                completed_at TEXT,
                cancelled_at TEXT
            );
            """
        )

        for user_id in range(1, 6):
            await db.execute(
                "INSERT INTO users (id, tg_id, full_name) VALUES (?, ?, ?)",
                (user_id, 900000000 + user_id, f"User {user_id}"),
            )
        await db.commit()

        payload_1 = {
            "to_user_id": 2,
            "scheduled_for": "2099-01-10T10:00:00",
            "format": "online",
            "location": None,
            "message": "invite one",
            "expires_at": None,
        }
        req_1 = await meeting_request_service.create_request(db, from_user_id=1, payload=payload_1)

        payload_2 = {
            "to_user_id": 3,
            "scheduled_for": "2099-01-12T11:00:00",
            "format": "offline",
            "location": None,
            "message": "invite two",
            "expires_at": None,
        }
        await meeting_request_service.create_request(db, from_user_id=1, payload=payload_2)

        payload_3 = {
            "to_user_id": 1,
            "scheduled_for": "2099-01-13T12:00:00",
            "format": "online",
            "location": None,
            "message": "incoming",
            "expires_at": None,
        }
        await meeting_request_service.create_request(db, from_user_id=4, payload=payload_3)

        accepted = await meeting_request_service.respond_request(db, request_id=int(req_1["id"]), actor_user_id=2, action="accept")
        await db.commit()

        assert accepted["request"]["status"] == "accepted"
        assert accepted["meeting"] is not None
        assert accepted["meeting"]["status"] == "scheduled"

        outgoing = await meeting_requests_repo.list_by_type(db, user_id=1, request_type="outgoing", limit=50)
        incoming = await meeting_requests_repo.list_by_type(db, user_id=1, request_type="incoming", only_pending=True, limit=50)

        assert len(outgoing) == 2
        assert len(incoming) == 1
