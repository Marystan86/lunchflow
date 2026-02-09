# main.py

import logging
import asyncio
import aiohttp
import aiosqlite
from app.config import DB_PATH
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles

from routes import router as api_router
from routes import survey_dispatcher_loop



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
                type TEXT NOT NULL,            -- например "invite_response"
                payload TEXT,                  -- json string с деталями
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

        # places (заведения)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                rating REAL DEFAULT 0.0,
                open_time TEXT,   -- формат "HH:MM"
                close_time TEXT,  -- формат "HH:MM"
                address TEXT,
                photo TEXT,       -- url к картинке
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

            # ждём либо событие стопа, либо таймаут - но таймаут не должен завершать таск с ошибкой
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        # ожидаемо при shutdown
        logger = logging.getLogger("root")
        logger.info("cleanup_task cancelled")
        return



@asynccontextmanager
async def lifespan(app: FastAPI):
    # инициализация БД
    await init_db()

    # глобальная http сессия для всего приложения (для Telegram и других запросов)
    import socket
    app.state.http_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=50, family=socket.AF_INET))

    stop_event = asyncio.Event()

    # один cleanup таск
    cleanup_t = asyncio.create_task(cleanup_task(stop_event))

    # стартуем survey worker; если survey_dispatcher_loop требует args - передайте их
    survey_task = asyncio.create_task(survey_dispatcher_loop())

    app.state._survey_task = survey_task
    app.state._cleanup_task = cleanup_t

    try:
        yield
    finally:
        # начинаем аккуратный shutdown
        stop_event.set()

        # отменяем таски и ждём их завершения аккуратно
        for t in (cleanup_t, survey_task):
            t.cancel()

        # дождёмся с обработкой CancelledError
        for t in (cleanup_t, survey_task):
            try:
                await t
            except asyncio.CancelledError:
                logging.info("Task %s cancelled", t.get_name() if hasattr(t, "get_name") else t)
            except Exception:
                logging.exception("Error awaiting task %s during shutdown", t)

        # закроем http сессию
        try:
            await app.state.http_session.close()
        except Exception:
            logging.exception("Error closing http_session")


app = FastAPI(lifespan=lifespan, title="meet&eat")
app.include_router(api_router)
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.middleware("http")
async def add_ngrok_header(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["ngrok-skip-browser-warning"] = "1"
    return resp