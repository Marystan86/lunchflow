from collections.abc import AsyncGenerator

import aiosqlite

from backend.app.settings import settings


USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE NOT NULL,
    source TEXT DEFAULT 'real',
    tg_username TEXT,
    full_name TEXT,
    photo_url TEXT,
    city TEXT,
    company TEXT,
    position TEXT,
    bio TEXT,
    help_tags TEXT,
    need_tags TEXT,
    contacts TEXT,
    visibility TEXT DEFAULT 'members_only',
    role TEXT DEFAULT 'member',
    is_admin INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    company_name TEXT,
    industry TEXT,
    annual_revenue TEXT,
    employee_count INTEGER,
    core_competencies TEXT,
    goal_2025 TEXT,
    club_request TEXT,
    hobbies TEXT,
    help_offer TEXT,
    created_at TEXT,
    updated_at TEXT
);
"""

BADGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    title TEXT,
    description TEXT,
    icon TEXT,
    badge_type TEXT DEFAULT 'system',
    grant_mode TEXT DEFAULT 'auto',
    criteria_type TEXT,
    criteria_value INTEGER,
    vote_threshold INTEGER,
    cooldown_days INTEGER DEFAULT 30,
    is_active INTEGER DEFAULT 1
);
"""

USER_BADGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS user_badges (
    user_id INTEGER NOT NULL,
    badge_id INTEGER NOT NULL,
    earned_at TEXT NOT NULL,
    UNIQUE(user_id, badge_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(badge_id) REFERENCES badges(id) ON DELETE CASCADE
);
"""

BADGE_VOTES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS badge_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    badge_id INTEGER NOT NULL,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER NOT NULL,
    meeting_id INTEGER NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(badge_id, from_user_id, to_user_id, meeting_id),
    FOREIGN KEY(badge_id) REFERENCES badges(id) ON DELETE CASCADE,
    FOREIGN KEY(from_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(to_user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

MEETINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS meetings (
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
    cancelled_at TEXT,
    CHECK(initiator_id != receiver_id),
    FOREIGN KEY(initiator_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(receiver_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

MEETING_REQUESTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS meeting_requests (
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
    updated_at TEXT NOT NULL,
    CHECK(from_user_id != to_user_id),
    FOREIGN KEY(from_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(to_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(responder_user_id) REFERENCES users(id) ON DELETE SET NULL
);
"""

MEETING_CONFIRMATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS meeting_confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    confirmation_status TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(meeting_id, user_id),
    CHECK(confirmation_status IN ('met', 'not_met')),
    FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    created_by_user_id INTEGER NOT NULL,
    created_by_role TEXT NOT NULL CHECK(created_by_role IN ('club', 'member')),
    created_source TEXT NOT NULL DEFAULT 'app',
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
    confirmed_at TEXT,
    FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE RESTRICT
);
"""

EVENT_PARTICIPANTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS event_participants (
    event_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    UNIQUE(event_id, user_id),
    FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

POINTS_LEDGER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS points_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    reason_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    meta TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

NEWS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS news (
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
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);
"""

STORE_CATEGORIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS store_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);
"""

STORE_PRODUCTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS store_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price_points INTEGER NOT NULL CHECK(price_points >= 0),
    is_active INTEGER NOT NULL DEFAULT 1,
    is_repeatable INTEGER NOT NULL DEFAULT 0,
    stock_limit INTEGER,
    per_user_limit INTEGER,
    image_key TEXT,
    badge_award_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(category_id) REFERENCES store_categories(id) ON DELETE RESTRICT,
    FOREIGN KEY(badge_award_id) REFERENCES badges(id) ON DELETE SET NULL
);
"""

STORE_ORDERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS store_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('created', 'paid', 'cancelled', 'fulfilled')),
    qty INTEGER NOT NULL DEFAULT 1 CHECK(qty > 0),
    total_points INTEGER NOT NULL CHECK(total_points >= 0),
    external_ref TEXT,
    is_repeatable_snapshot INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY(product_id) REFERENCES store_products(id) ON DELETE RESTRICT
);
"""


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    db = await aiosqlite.connect(settings.db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA busy_timeout = 5000;")
    await db.execute("PRAGMA foreign_keys = ON;")
    try:
        yield db
    finally:
        await db.close()


async def _column_exists(db: aiosqlite.Connection, table: str, column: str) -> bool:
    cur = await db.execute(f"PRAGMA table_info({table})")
    rows = await cur.fetchall()
    return any(str(row[1]) == column for row in rows)


async def _ensure_community_admin_user(db: aiosqlite.Connection) -> int:
    cur = await db.execute(
        """
        SELECT id
        FROM users
        WHERE role IN ('community_admin', 'superadmin', 'admin')
           OR is_admin = 1
        ORDER BY id
        LIMIT 1
        """
    )
    row = await cur.fetchone()
    if row:
        return int(row[0])

    tg_id = 999000999
    cur = await db.execute("SELECT id FROM users WHERE tg_id = ? LIMIT 1", (tg_id,))
    existing = await cur.fetchone()
    if existing:
        user_id = int(existing[0])
        await db.execute(
            """
            UPDATE users
            SET role = 'community_admin', is_admin = 1, status = 'active', source = COALESCE(source, 'real'),
                full_name = COALESCE(full_name, 'Комьюнити-админ'),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (user_id,),
        )
        return user_id

    cur = await db.execute(
        """
        INSERT INTO users (
            tg_id, source, tg_username, full_name, role, is_admin, status, created_at, updated_at
        ) VALUES (?, 'real', 'community_admin_999', 'Комьюнити-админ', 'community_admin', 1, 'active', datetime('now'), datetime('now'))
        """,
        (tg_id,),
    )
    return int(cur.lastrowid)


async def _migrate_events_table(db: aiosqlite.Connection, admin_user_id: int) -> None:
    has_role = await _column_exists(db, "events", "created_by_role")
    has_creator = await _column_exists(db, "events", "created_by_user_id")
    has_source = await _column_exists(db, "events", "created_source")
    has_label = await _column_exists(db, "events", "club_label")
    if has_role and has_creator and has_source and has_label:
        return

    has_owner = await _column_exists(db, "events", "owner_id")
    has_created_by = await _column_exists(db, "events", "created_by")
    has_is_club = await _column_exists(db, "events", "is_club_event")
    has_title = await _column_exists(db, "events", "title")
    has_description = await _column_exists(db, "events", "description")
    has_category = await _column_exists(db, "events", "category")
    has_event_type = await _column_exists(db, "events", "event_type")
    has_city = await _column_exists(db, "events", "city")
    has_location = await _column_exists(db, "events", "location")
    has_tags = await _column_exists(db, "events", "tags")
    has_capacity = await _column_exists(db, "events", "capacity")
    has_starts_at = await _column_exists(db, "events", "starts_at")
    has_status = await _column_exists(db, "events", "status")
    has_created_at = await _column_exists(db, "events", "created_at")
    has_confirmed_at = await _column_exists(db, "events", "confirmed_at")

    await db.execute("PRAGMA foreign_keys = OFF;")
    await db.execute("DROP TABLE IF EXISTS events_new;")
    await db.execute(
        """
        CREATE TABLE events_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            created_by_user_id INTEGER NOT NULL,
            created_by_role TEXT NOT NULL CHECK(created_by_role IN ('club', 'member')),
            created_source TEXT NOT NULL DEFAULT 'app',
            club_label TEXT,
            is_club_event INTEGER NOT NULL DEFAULT 0 CHECK(is_club_event IN (0, 1)),
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
            confirmed_at TEXT,
            FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE RESTRICT
        );
        """
    )

    owner_expr = "e.owner_id" if has_owner else ("e.created_by" if has_created_by else str(int(admin_user_id)))
    created_by_expr = "e.created_by" if has_created_by else owner_expr
    is_club_expr = "e.is_club_event" if has_is_club else "1"
    title_expr = "e.title" if has_title else "'Событие'"
    description_expr = "e.description" if has_description else "NULL"
    category_expr = "e.category" if has_category else "NULL"
    event_type_expr = "e.event_type" if has_event_type else "'offline'"
    city_expr = "e.city" if has_city else "NULL"
    location_expr = "e.location" if has_location else "NULL"
    tags_expr = "e.tags" if has_tags else "NULL"
    capacity_expr = "e.capacity" if has_capacity else "10"
    starts_at_expr = "e.starts_at" if has_starts_at else ("e.created_at" if has_created_at else "datetime('now')")
    status_expr = "e.status" if has_status else "'published'"
    created_at_expr = "e.created_at" if has_created_at else "datetime('now')"
    confirmed_at_expr = "e.confirmed_at" if has_confirmed_at else "NULL"

    await db.execute(
        f"""
        INSERT INTO events_new (
            id, owner_id, created_by_user_id, created_by_role, created_source, club_label, is_club_event,
            title, description, category, city, location, tags, event_type, capacity, starts_at, status, created_at, confirmed_at
        )
        SELECT
            e.id,
            COALESCE({owner_expr}, {int(admin_user_id)}) AS owner_id,
            COALESCE({created_by_expr}, {owner_expr}, {int(admin_user_id)}) AS created_by_user_id,
            CASE
                WHEN COALESCE({is_club_expr}, 1) = 1 THEN 'club'
                ELSE 'member'
            END AS created_by_role,
            'app' AS created_source,
            CASE WHEN COALESCE({is_club_expr}, 1) = 1 THEN 'Клуб 999' ELSE NULL END AS club_label,
            CASE WHEN COALESCE({is_club_expr}, 1) = 1 THEN 1 ELSE 0 END AS is_club_event,
            COALESCE({title_expr}, 'Событие') AS title,
            {description_expr},
            {category_expr},
            {city_expr},
            {location_expr},
            {tags_expr},
            COALESCE({event_type_expr}, 'offline') AS event_type,
            COALESCE({capacity_expr}, 10) AS capacity,
            COALESCE({starts_at_expr}, {created_at_expr}, datetime('now')) AS starts_at,
            COALESCE({status_expr}, 'published') AS status,
            COALESCE({created_at_expr}, datetime('now')) AS created_at,
            {confirmed_at_expr}
        FROM events e;
        """
    )
    await db.execute("DROP TABLE events;")
    await db.execute("ALTER TABLE events_new RENAME TO events;")
    await db.execute("PRAGMA foreign_keys = ON;")


async def _create_events_integrity_triggers(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_events_role_club_insert
        BEFORE INSERT ON events
        FOR EACH ROW
        WHEN NEW.created_by_role = 'club' AND NEW.is_club_event != 1
        BEGIN
            SELECT RAISE(ABORT, 'club event must have is_club_event=1');
        END
        """
    )
    await db.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_events_role_member_insert
        BEFORE INSERT ON events
        FOR EACH ROW
        WHEN NEW.created_by_role = 'member' AND NEW.is_club_event != 0
        BEGIN
            SELECT RAISE(ABORT, 'member event must have is_club_event=0');
        END
        """
    )
    await db.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_events_role_club_update
        BEFORE UPDATE ON events
        FOR EACH ROW
        WHEN NEW.created_by_role = 'club' AND NEW.is_club_event != 1
        BEGIN
            SELECT RAISE(ABORT, 'club event must have is_club_event=1');
        END
        """
    )
    await db.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_events_role_member_update
        BEFORE UPDATE ON events
        FOR EACH ROW
        WHEN NEW.created_by_role = 'member' AND NEW.is_club_event != 0
        BEGIN
            SELECT RAISE(ABORT, 'member event must have is_club_event=0');
        END
        """
    )


async def _create_store_integrity_triggers(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_store_orders_set_repeatable_snapshot_insert
        AFTER INSERT ON store_orders
        FOR EACH ROW
        BEGIN
            UPDATE store_orders
            SET is_repeatable_snapshot = COALESCE(
                (SELECT is_repeatable FROM store_products WHERE id = NEW.product_id),
                0
            )
            WHERE id = NEW.id;
        END
        """
    )
    await db.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_store_orders_prevent_nonrepeatable_duplicate_insert
        BEFORE INSERT ON store_orders
        FOR EACH ROW
        WHEN COALESCE((SELECT is_repeatable FROM store_products WHERE id = NEW.product_id), 0) = 0
             AND EXISTS (
                SELECT 1
                FROM store_orders so
                WHERE so.user_id = NEW.user_id
                  AND so.product_id = NEW.product_id
                  AND so.status IN ('paid', 'fulfilled')
             )
        BEGIN
            SELECT RAISE(ABORT, 'non-repeatable product already purchased');
        END
        """
    )


async def _seed_store_catalog(db: aiosqlite.Connection) -> None:
    categories = [
        ("all", "Все", 0),
        ("services", "Сервисы", 10),
        ("mentoring", "Менторство", 20),
        ("merch", "Атрибутика", 30),
        ("partners", "Партнёры", 40),
    ]
    for slug, title, sort_order in categories:
        await db.execute(
            """
            INSERT INTO store_categories (slug, title, sort_order, is_active)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                sort_order = excluded.sort_order,
                is_active = 1
            """,
            (slug, title, int(sort_order)),
        )

    products = [
        ("mentoring", "Разбор от Олега", "Личный разбор вашего кейса/вопроса (20-30 минут).", 50, 1, 1, None, None, "mentor_oleg_review"),
        ("mentoring", "Трекерство на месяц", "Сопровождение на 1 месяц: еженедельные чек-ины и фокус.", 150, 1, 1, None, 1, "tracker_month"),
        ("merch", "Футболка 999", "Клубная футболка с символикой 999.", 20, 0, 1, 15, 1, "tshirt_999"),
        ("merch", "Ручка 999", "Клубная ручка 999 (металлик/премиум).", 5, 0, 1, 39, 2, "pen_999"),
        ("services", "VIP место на групповую встречу", "Приоритетная запись на ближайший групповой мастермайнд.", 30, 1, 1, 10, None, "vip_group_slot"),
        ("partners", "Скидка от партнёра: Кофейня", "Скидка 15% в партнёрской кофейне.", 10, 0, 1, 50, 1, "partner_coffee_discount"),
        ("services", "Билет на закрытый ивент", "Доступ на закрытый клубный формат (ограничено).", 60, 0, 1, 8, 1, "closed_event_ticket"),
    ]
    for category_slug, title, description, price, is_repeatable, is_active, stock_limit, per_user_limit, image_key in products:
        await db.execute(
            """
            INSERT INTO store_products (
                category_id, title, description, price_points, is_active, is_repeatable,
                stock_limit, per_user_limit, image_key, badge_award_id, created_at, updated_at
            )
            VALUES (
                (SELECT id FROM store_categories WHERE slug = ?),
                ?, ?, ?, ?, ?, ?, ?, ?, NULL, datetime('now'), datetime('now')
            )
            ON CONFLICT(title) DO UPDATE SET
                category_id = excluded.category_id,
                description = excluded.description,
                price_points = excluded.price_points,
                is_active = excluded.is_active,
                is_repeatable = excluded.is_repeatable,
                stock_limit = excluded.stock_limit,
                per_user_limit = excluded.per_user_limit,
                image_key = excluded.image_key,
                updated_at = datetime('now')
            """,
            (
                category_slug,
                title,
                description,
                int(price),
                int(is_active),
                int(is_repeatable),
                stock_limit,
                per_user_limit,
                image_key,
            ),
        )


async def init_db() -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA busy_timeout = 5000;")
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute(USERS_TABLE_SQL)
        await db.execute(BADGES_TABLE_SQL)
        await db.execute(USER_BADGES_TABLE_SQL)
        await db.execute(BADGE_VOTES_TABLE_SQL)
        await db.execute(MEETINGS_TABLE_SQL)
        await db.execute(MEETING_REQUESTS_TABLE_SQL)
        await db.execute(MEETING_CONFIRMATIONS_TABLE_SQL)
        await db.execute(EVENTS_TABLE_SQL)
        await db.execute(EVENT_PARTICIPANTS_TABLE_SQL)
        await db.execute(POINTS_LEDGER_TABLE_SQL)
        await db.execute(NEWS_TABLE_SQL)
        await db.execute(STORE_CATEGORIES_TABLE_SQL)
        await db.execute(STORE_PRODUCTS_TABLE_SQL)
        await db.execute(STORE_ORDERS_TABLE_SQL)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_news_created_at ON news(created_at DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_news_entity ON news(entity_type, entity_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_meetings_pair ON meetings(initiator_id, receiver_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_events_owner ON events(owner_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_points_user ON points_ledger(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_products_category_id ON store_products(category_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_products_is_active ON store_products(is_active)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON store_orders(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_product_id ON store_orders(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON store_orders(status)")
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_store_products_title ON store_products(title)")
        await db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_store_orders_nonrepeat_paid
            ON store_orders(user_id, product_id)
            WHERE status IN ('paid', 'fulfilled') AND is_repeatable_snapshot = 0
            """
        )
        # Soft migration for existing users table.
        for alter_sql in (
            "ALTER TABLE users ADD COLUMN source TEXT DEFAULT 'real'",
            "ALTER TABLE users ADD COLUMN tg_username TEXT",
            "ALTER TABLE users ADD COLUMN full_name TEXT",
            "ALTER TABLE users ADD COLUMN photo_url TEXT",
            "ALTER TABLE users ADD COLUMN city TEXT",
            "ALTER TABLE users ADD COLUMN company TEXT",
            "ALTER TABLE users ADD COLUMN position TEXT",
            "ALTER TABLE users ADD COLUMN bio TEXT",
            "ALTER TABLE users ADD COLUMN help_tags TEXT",
            "ALTER TABLE users ADD COLUMN need_tags TEXT",
            "ALTER TABLE users ADD COLUMN contacts TEXT",
            "ALTER TABLE users ADD COLUMN visibility TEXT DEFAULT 'members_only'",
            "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'member'",
            "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'pending'",
            "ALTER TABLE users ADD COLUMN company_name TEXT",
            "ALTER TABLE users ADD COLUMN industry TEXT",
            "ALTER TABLE users ADD COLUMN annual_revenue TEXT",
            "ALTER TABLE users ADD COLUMN employee_count INTEGER",
            "ALTER TABLE users ADD COLUMN core_competencies TEXT",
            "ALTER TABLE users ADD COLUMN goal_2025 TEXT",
            "ALTER TABLE users ADD COLUMN club_request TEXT",
            "ALTER TABLE users ADD COLUMN hobbies TEXT",
            "ALTER TABLE users ADD COLUMN help_offer TEXT",
            "ALTER TABLE users ADD COLUMN created_at TEXT",
            "ALTER TABLE users ADD COLUMN updated_at TEXT",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        for alter_sql in (
            "ALTER TABLE badges ADD COLUMN badge_type TEXT DEFAULT 'system'",
            "ALTER TABLE badges ADD COLUMN grant_mode TEXT DEFAULT 'auto'",
            "ALTER TABLE badges ADD COLUMN criteria_type TEXT",
            "ALTER TABLE badges ADD COLUMN criteria_value INTEGER",
            "ALTER TABLE badges ADD COLUMN vote_threshold INTEGER",
            "ALTER TABLE badges ADD COLUMN cooldown_days INTEGER DEFAULT 30",
            "ALTER TABLE badges ADD COLUMN is_active INTEGER DEFAULT 1",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        for alter_sql in (
            "ALTER TABLE news ADD COLUMN tag TEXT",
            "ALTER TABLE news ADD COLUMN media_urls TEXT",
            "ALTER TABLE news ADD COLUMN entity_type TEXT",
            "ALTER TABLE news ADD COLUMN entity_id INTEGER",
            "ALTER TABLE news ADD COLUMN created_by_user_id INTEGER",
            "ALTER TABLE news ADD COLUMN is_pinned INTEGER DEFAULT 0",
            "ALTER TABLE news ADD COLUMN is_active INTEGER DEFAULT 1",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        for alter_sql in (
            "ALTER TABLE meetings ADD COLUMN initiator_id INTEGER",
            "ALTER TABLE meetings ADD COLUMN receiver_id INTEGER",
            "ALTER TABLE meetings ADD COLUMN status TEXT",
            "ALTER TABLE meetings ADD COLUMN created_at TEXT",
            "ALTER TABLE meetings ADD COLUMN confirmed_at TEXT",
            "ALTER TABLE meetings ADD COLUMN request_id INTEGER",
            "ALTER TABLE meetings ADD COLUMN participant_a_id INTEGER",
            "ALTER TABLE meetings ADD COLUMN participant_b_id INTEGER",
            "ALTER TABLE meetings ADD COLUMN scheduled_for TEXT",
            "ALTER TABLE meetings ADD COLUMN format TEXT",
            "ALTER TABLE meetings ADD COLUMN location TEXT",
            "ALTER TABLE meetings ADD COLUMN notes TEXT",
            "ALTER TABLE meetings ADD COLUMN completed_at TEXT",
            "ALTER TABLE meetings ADD COLUMN cancelled_at TEXT",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        for alter_sql in (
            "ALTER TABLE events ADD COLUMN owner_id INTEGER",
            "ALTER TABLE events ADD COLUMN created_by INTEGER",
            "ALTER TABLE events ADD COLUMN created_by_user_id INTEGER",
            "ALTER TABLE events ADD COLUMN created_by_role TEXT DEFAULT 'member'",
            "ALTER TABLE events ADD COLUMN created_source TEXT DEFAULT 'app'",
            "ALTER TABLE events ADD COLUMN club_label TEXT",
            "ALTER TABLE events ADD COLUMN is_club_event INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE events ADD COLUMN title TEXT",
            "ALTER TABLE events ADD COLUMN description TEXT",
            "ALTER TABLE events ADD COLUMN category TEXT",
            "ALTER TABLE events ADD COLUMN city TEXT",
            "ALTER TABLE events ADD COLUMN location TEXT",
            "ALTER TABLE events ADD COLUMN tags TEXT",
            "ALTER TABLE events ADD COLUMN event_type TEXT",
            "ALTER TABLE events ADD COLUMN capacity INTEGER",
            "ALTER TABLE events ADD COLUMN starts_at TEXT",
            "ALTER TABLE events ADD COLUMN status TEXT",
            "ALTER TABLE events ADD COLUMN created_at TEXT",
            "ALTER TABLE events ADD COLUMN confirmed_at TEXT",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        for alter_sql in (
            "ALTER TABLE event_participants ADD COLUMN event_id INTEGER",
            "ALTER TABLE event_participants ADD COLUMN user_id INTEGER",
            "ALTER TABLE event_participants ADD COLUMN status TEXT",
            "ALTER TABLE event_participants ADD COLUMN joined_at TEXT",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        for alter_sql in (
            "ALTER TABLE points_ledger ADD COLUMN user_id INTEGER",
            "ALTER TABLE points_ledger ADD COLUMN amount INTEGER",
            "ALTER TABLE points_ledger ADD COLUMN reason_type TEXT",
            "ALTER TABLE points_ledger ADD COLUMN entity_type TEXT",
            "ALTER TABLE points_ledger ADD COLUMN entity_id INTEGER",
            "ALTER TABLE points_ledger ADD COLUMN meta TEXT",
            "ALTER TABLE points_ledger ADD COLUMN created_at TEXT",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        for alter_sql in (
            "ALTER TABLE store_products ADD COLUMN category_id INTEGER",
            "ALTER TABLE store_products ADD COLUMN title TEXT",
            "ALTER TABLE store_products ADD COLUMN description TEXT",
            "ALTER TABLE store_products ADD COLUMN price_points INTEGER",
            "ALTER TABLE store_products ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE store_products ADD COLUMN is_repeatable INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE store_products ADD COLUMN stock_limit INTEGER",
            "ALTER TABLE store_products ADD COLUMN per_user_limit INTEGER",
            "ALTER TABLE store_products ADD COLUMN image_key TEXT",
            "ALTER TABLE store_products ADD COLUMN badge_award_id INTEGER",
            "ALTER TABLE store_products ADD COLUMN created_at TEXT",
            "ALTER TABLE store_products ADD COLUMN updated_at TEXT",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        for alter_sql in (
            "ALTER TABLE store_orders ADD COLUMN user_id INTEGER",
            "ALTER TABLE store_orders ADD COLUMN product_id INTEGER",
            "ALTER TABLE store_orders ADD COLUMN status TEXT",
            "ALTER TABLE store_orders ADD COLUMN qty INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE store_orders ADD COLUMN total_points INTEGER",
            "ALTER TABLE store_orders ADD COLUMN external_ref TEXT",
            "ALTER TABLE store_orders ADD COLUMN is_repeatable_snapshot INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE store_orders ADD COLUMN created_at TEXT",
            "ALTER TABLE store_orders ADD COLUMN updated_at TEXT",
        ):
            try:
                await db.execute(alter_sql)
            except Exception:
                pass

        for ddl_sql in (
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_meeting_requests_pending_pair
            ON meeting_requests(
                CASE WHEN from_user_id < to_user_id THEN from_user_id ELSE to_user_id END,
                CASE WHEN from_user_id < to_user_id THEN to_user_id ELSE from_user_id END
            )
            WHERE status = 'pending'
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_meeting_requests_active_pair
            ON meeting_requests(
                CASE WHEN from_user_id < to_user_id THEN from_user_id ELSE to_user_id END,
                CASE WHEN from_user_id < to_user_id THEN to_user_id ELSE from_user_id END
            )
            WHERE status IN ('pending', 'accepted')
            """,
            "CREATE INDEX IF NOT EXISTS idx_meeting_requests_from_status ON meeting_requests(from_user_id, status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_meeting_requests_to_status ON meeting_requests(to_user_id, status, created_at DESC)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_meetings_request_id ON meetings(request_id) WHERE request_id IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_meetings_status_sched ON meetings(status, scheduled_for)",
            "CREATE INDEX IF NOT EXISTS idx_meeting_confirmations_meeting ON meeting_confirmations(meeting_id)",
            "CREATE INDEX IF NOT EXISTS idx_events_created_by_user_id ON events(created_by_user_id)",
            "CREATE INDEX IF NOT EXISTS idx_events_is_club_event ON events(is_club_event)",
            "CREATE INDEX IF NOT EXISTS idx_events_starts_at ON events(starts_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_events_club_starts ON events(is_club_event, starts_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_event_participants_user_status ON event_participants(user_id, status)",
            """
            CREATE TRIGGER IF NOT EXISTS trg_meetings_participants_not_equal_insert
            BEFORE INSERT ON meetings
            FOR EACH ROW
            WHEN COALESCE(NEW.participant_a_id, NEW.initiator_id) = COALESCE(NEW.participant_b_id, NEW.receiver_id)
            BEGIN
                SELECT RAISE(ABORT, 'participant_a_id must differ from participant_b_id');
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_meetings_participants_not_equal_update
            BEFORE UPDATE ON meetings
            FOR EACH ROW
            WHEN COALESCE(NEW.participant_a_id, NEW.initiator_id) = COALESCE(NEW.participant_b_id, NEW.receiver_id)
            BEGIN
                SELECT RAISE(ABORT, 'participant_a_id must differ from participant_b_id');
            END
            """,
        ):
            try:
                await db.execute(ddl_sql)
            except Exception:
                pass

        # Backfill legacy columns if present in old schema.
        for update_sql in (
            "UPDATE users SET full_name = COALESCE(full_name, name)",
            "UPDATE users SET photo_url = COALESCE(photo_url, avatar)",
            "UPDATE users SET tg_username = COALESCE(tg_username, username)",
            "UPDATE users SET created_at = COALESCE(created_at, datetime('now'))",
            "UPDATE users SET updated_at = COALESCE(updated_at, datetime('now'))",
            "UPDATE users SET source = COALESCE(source, 'real')",
            "UPDATE users SET visibility = COALESCE(visibility, 'members_only')",
            "UPDATE users SET role = COALESCE(role, 'member')",
            "UPDATE users SET is_admin = CASE WHEN role IN ('admin', 'superadmin', 'community_admin') THEN 1 ELSE COALESCE(is_admin, 0) END",
            "UPDATE users SET status = COALESCE(status, 'pending')",
            "UPDATE badges SET badge_type = COALESCE(badge_type, 'system')",
            "UPDATE badges SET grant_mode = COALESCE(grant_mode, 'auto')",
            "UPDATE badges SET cooldown_days = COALESCE(cooldown_days, 30)",
            "UPDATE badges SET is_active = COALESCE(is_active, 1)",
            "UPDATE news SET tag = COALESCE(tag, CASE type WHEN 'admin_post' THEN 'Клуб' WHEN 'event_announcement' THEN 'Ивент' WHEN 'event_summary' THEN 'Итоги' ELSE NULL END)",
            "UPDATE news SET is_pinned = COALESCE(is_pinned, 0)",
            "UPDATE news SET is_active = COALESCE(is_active, 1)",
            "UPDATE meetings SET participant_a_id = COALESCE(participant_a_id, initiator_id)",
            "UPDATE meetings SET participant_b_id = COALESCE(participant_b_id, receiver_id)",
            "UPDATE meetings SET scheduled_for = COALESCE(scheduled_for, confirmed_at, created_at)",
            "UPDATE events SET created_by = COALESCE(created_by, owner_id)",
            "UPDATE events SET created_by_user_id = COALESCE(created_by_user_id, created_by, owner_id)",
            "UPDATE events SET created_by_role = COALESCE(created_by_role, CASE WHEN is_club_event = 1 THEN 'club' ELSE 'member' END)",
            "UPDATE events SET created_source = COALESCE(created_source, 'app')",
            "UPDATE events SET club_label = COALESCE(club_label, CASE WHEN is_club_event = 1 THEN 'Клуб 999' ELSE NULL END)",
            "UPDATE events SET is_club_event = CASE WHEN COALESCE(created_by_role, 'member') = 'club' THEN 1 ELSE 0 END",
        ):
            try:
                await db.execute(update_sql)
            except Exception:
                pass

        admin_user_id = await _ensure_community_admin_user(db)
        await _migrate_events_table(db, admin_user_id=admin_user_id)
        await _create_events_integrity_triggers(db)
        await _create_store_integrity_triggers(db)
        await _seed_store_catalog(db)

        await db.execute(
            "UPDATE events SET created_by_user_id = COALESCE(created_by_user_id, owner_id, ?)",
            (int(admin_user_id),),
        )
        await db.execute(
            "UPDATE events SET created_by_role = COALESCE(created_by_role, CASE WHEN is_club_event = 1 THEN 'club' ELSE 'member' END)"
        )
        await db.execute("UPDATE events SET created_source = COALESCE(created_source, 'app')")
        await db.execute(
            "UPDATE events SET club_label = COALESCE(club_label, CASE WHEN created_by_role = 'club' THEN 'Клуб 999' ELSE NULL END)"
        )
        await db.execute(
            "UPDATE events SET is_club_event = CASE WHEN created_by_role = 'club' THEN 1 ELSE 0 END"
        )

        await db.commit()

