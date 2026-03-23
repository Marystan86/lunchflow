# main.py

import logging
import asyncio
import aiohttp
import aiosqlite
from app.config import DB_PATH
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
load_dotenv()

from routes import router as legacy_router
from routes import survey_dispatcher_loop
from backend.app.api import api_router
from backend.app.db import init_db as init_backend_db
from backend.app.settings import settings as backend_settings
from backend.app.services import badges_service
from backend.app.tasks.scheduler import survey_scheduler_loop



async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout = 5000;")  # ms
        await db.commit()

        # users table (age may be added if missing)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                avatar TEXT,
                username TEXT,
                age INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        # Legacy-safe: add missing users columns when running on older DBs.
        for alter_sql in (
            "ALTER TABLE users ADD COLUMN username TEXT",
            "ALTER TABLE users ADD COLUMN name TEXT",
            "ALTER TABLE users ADD COLUMN avatar TEXT",
            "ALTER TABLE users ADD COLUMN age INTEGER",
            "ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT (datetime('now'))",
            "ALTER TABLE users ADD COLUMN updated_at TEXT DEFAULT (datetime('now'))",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        await db.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                full_name TEXT,
                title TEXT,
                services TEXT,
                monthly_turnover_range TEXT,
                yearly_turnover_range TEXT,
                team_size TEXT,
                key_competencies TEXT,
                club_audience_request TEXT,
                hobbies TEXT,
                help_topics TEXT,
                instagram_handle TEXT,
                qr_url TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        # user_tags for interests
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                UNIQUE(user_id, tag),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)

        # eat_sessions unchanged
        await db.execute("""
            CREATE TABLE IF NOT EXISTS eat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                started_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_tags_tag 
                ON user_tags(tag);
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,            -- РЅР°РїСЂРёРјРµСЂ "invite_response"
                payload TEXT,                  -- json string СЃ РґРµС‚Р°Р»СЏРјРё
                read INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                time_iso TEXT,
                meal_type TEXT,
                place_id INTEGER,
                place_name TEXT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                responder_user_id INTEGER,
                responded_at TEXT,
                survey_sent INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(from_user_id) REFERENCES users(id),
                FOREIGN KEY(to_user_id) REFERENCES users(id)
            );
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_invites_to 
                ON invites(to_user_id);
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invite_surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invite_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                answer TEXT NOT NULL,
                created_at DATETIME DEFAULT (datetime('now'))
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reviewer_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                reaction TEXT NOT NULL,
                comment TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(reviewer_id) REFERENCES users(id),
                FOREIGN KEY(target_user_id) REFERENCES users(id),
                UNIQUE(reviewer_id, target_user_id, reaction)
            );
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reviews_target 
                ON reviews(target_user_id);
        """)

        # places (Р·Р°РІРµРґРµРЅРёСЏ)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                rating REAL DEFAULT 0.0,
                open_time TEXT,   -- С„РѕСЂРјР°С‚ "HH:MM"
                close_time TEXT,  -- С„РѕСЂРјР°С‚ "HH:MM"
                address TEXT,
                photo TEXT,       -- url Рє РєР°СЂС‚РёРЅРєРµ
                created_by_tg_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_places_category ON places(category);
        """)

        await db.commit()

        try:
            await db.commit()
        except Exception:
            pass


async def cleanup_task(stop_event: asyncio.Event):
    try:
        while not stop_event.is_set():
            try:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute(
                        "UPDATE eat_sessions SET active = 0 WHERE expires_at <= datetime('now') AND active = 1"
                    )
                    await db.commit()
            except Exception as e:
                logger = logging.getLogger("root")
                logger.exception("cleanup_task: db update failed: %s", e)

            # Р¶РґС‘Рј Р»РёР±Рѕ СЃРѕР±С‹С‚РёРµ СЃС‚РѕРїР°, Р»РёР±Рѕ С‚Р°Р№РјР°СѓС‚ - РЅРѕ С‚Р°Р№РјР°СѓС‚ РЅРµ РґРѕР»Р¶РµРЅ Р·Р°РІРµСЂС€Р°С‚СЊ С‚Р°СЃРє СЃ РѕС€РёР±РєРѕР№
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        # РѕР¶РёРґР°РµРјРѕ РїСЂРё shutdown
        logger = logging.getLogger("root")
        logger.info("cleanup_task cancelled")
        return



@asynccontextmanager
async def lifespan(app: FastAPI):
    # РёРЅРёС†РёР°Р»РёР·Р°С†РёСЏ Р‘Р”
    await init_db()
    await init_backend_db()
    await badges_service.ensure_seed()

    # РіР»РѕР±Р°Р»СЊРЅР°СЏ http СЃРµСЃСЃРёСЏ РґР»СЏ РІСЃРµРіРѕ РїСЂРёР»РѕР¶РµРЅРёСЏ (РґР»СЏ Telegram Рё РґСЂСѓРіРёС… Р·Р°РїСЂРѕСЃРѕРІ)
    import socket
    app.state.http_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=50, family=socket.AF_INET))

    stop_event = asyncio.Event()

    # РѕРґРёРЅ cleanup С‚Р°СЃРє
    cleanup_t = asyncio.create_task(cleanup_task(stop_event))

    # СЃС‚Р°СЂС‚СѓРµРј survey worker; РµСЃР»Рё survey_dispatcher_loop С‚СЂРµР±СѓРµС‚ args - РїРµСЂРµРґР°Р№С‚Рµ РёС…
    survey_task = asyncio.create_task(survey_dispatcher_loop())
    new_survey_task = None
    if backend_settings.survey_scheduler_enabled:
        new_survey_task = asyncio.create_task(
            survey_scheduler_loop(stop_event=stop_event, session=app.state.http_session)
        )

    app.state._survey_task = survey_task
    app.state._cleanup_task = cleanup_t
    app.state._new_survey_task = new_survey_task

    try:
        yield
    finally:
        # РЅР°С‡РёРЅР°РµРј Р°РєРєСѓСЂР°С‚РЅС‹Р№ shutdown
        stop_event.set()

        # РѕС‚РјРµРЅСЏРµРј С‚Р°СЃРєРё Рё Р¶РґС‘Рј РёС… Р·Р°РІРµСЂС€РµРЅРёСЏ Р°РєРєСѓСЂР°С‚РЅРѕ
        tasks_to_cancel = [cleanup_t, survey_task]
        if new_survey_task is not None:
            tasks_to_cancel.append(new_survey_task)

        for t in tasks_to_cancel:
            t.cancel()

        # РґРѕР¶РґС‘РјСЃСЏ СЃ РѕР±СЂР°Р±РѕС‚РєРѕР№ CancelledError
        for t in tasks_to_cancel:
            try:
                await t
            except asyncio.CancelledError:
                logging.info("Task %s cancelled", t.get_name() if hasattr(t, "get_name") else t)
            except Exception:
                logging.exception("Error awaiting task %s during shutdown", t)

        # Р·Р°РєСЂРѕРµРј http СЃРµСЃСЃРёСЋ
        try:
            await app.state.http_session.close()
        except Exception:
            logging.exception("Error closing http_session")


app = FastAPI(lifespan=lifespan, title="meet&eat")
app.include_router(legacy_router)
app.include_router(api_router, prefix="/api")
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.middleware("http")
async def add_ngrok_header(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["ngrok-skip-browser-warning"] = "1"
    return resp

