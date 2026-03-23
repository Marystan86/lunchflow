from datetime import datetime

import aiosqlite


async def list_categories(db: aiosqlite.Connection) -> list[dict]:
    cur = await db.execute(
        """
        SELECT id, slug, title, sort_order, is_active
        FROM store_categories
        WHERE is_active = 1
        ORDER BY sort_order ASC, id ASC
        """
    )
    return [dict(r) for r in await cur.fetchall()]


async def list_products(
    db: aiosqlite.Connection,
    *,
    category_slug: str | None,
    only_active: bool = True,
) -> list[dict]:
    where = []
    params: list = []
    if only_active:
        where.append("p.is_active = 1")
    if category_slug and category_slug != "all":
        where.append("c.slug = ?")
        params.append(category_slug)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    cur = await db.execute(
        f"""
        SELECT
            p.*,
            c.slug AS category_slug,
            c.title AS category_title,
            (
                SELECT COUNT(*)
                FROM store_orders so
                WHERE so.product_id = p.id AND so.status IN ('paid', 'fulfilled')
            ) AS paid_count
        FROM store_products p
        JOIN store_categories c ON c.id = p.category_id
        {where_sql}
        ORDER BY c.sort_order ASC, p.id ASC
        """,
        tuple(params),
    )
    return [dict(r) for r in await cur.fetchall()]


async def get_product_by_id(db: aiosqlite.Connection, product_id: int) -> dict | None:
    cur = await db.execute(
        """
        SELECT
            p.*,
            c.slug AS category_slug,
            c.title AS category_title,
            (
                SELECT COUNT(*)
                FROM store_orders so
                WHERE so.product_id = p.id AND so.status IN ('paid', 'fulfilled')
            ) AS paid_count
        FROM store_products p
        JOIN store_categories c ON c.id = p.category_id
        WHERE p.id = ?
        LIMIT 1
        """,
        (int(product_id),),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_nonrepeat_paid_order(db: aiosqlite.Connection, user_id: int, product_id: int) -> dict | None:
    cur = await db.execute(
        """
        SELECT *
        FROM store_orders
        WHERE user_id = ? AND product_id = ? AND status IN ('paid', 'fulfilled')
        ORDER BY id DESC
        LIMIT 1
        """,
        (int(user_id), int(product_id)),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def count_user_product_paid_orders(db: aiosqlite.Connection, user_id: int, product_id: int) -> int:
    cur = await db.execute(
        """
        SELECT COUNT(*)
        FROM store_orders
        WHERE user_id = ? AND product_id = ? AND status IN ('paid', 'fulfilled')
        """,
        (int(user_id), int(product_id)),
    )
    row = await cur.fetchone()
    return int(row[0] if row else 0)


async def create_order(
    db: aiosqlite.Connection,
    *,
    user_id: int,
    product_id: int,
    qty: int,
    total_points: int,
    status: str = "paid",
    is_repeatable_snapshot: int = 0,
) -> dict:
    now_iso = datetime.utcnow().isoformat()
    cur = await db.execute(
        """
        INSERT INTO store_orders (
            user_id, product_id, status, qty, total_points, external_ref, is_repeatable_snapshot, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)
        """,
        (
            int(user_id),
            int(product_id),
            status,
            int(qty),
            int(total_points),
            int(is_repeatable_snapshot),
            now_iso,
            now_iso,
        ),
    )
    return await get_order_by_id(db, int(cur.lastrowid))


async def get_order_by_id(db: aiosqlite.Connection, order_id: int) -> dict | None:
    cur = await db.execute("SELECT * FROM store_orders WHERE id = ? LIMIT 1", (int(order_id),))
    row = await cur.fetchone()
    return dict(row) if row else None


async def list_user_orders(db: aiosqlite.Connection, user_id: int) -> list[dict]:
    cur = await db.execute(
        """
        SELECT
            so.*,
            p.title AS product_title,
            p.description AS product_description,
            p.image_key AS image_key,
            c.title AS category_title
        FROM store_orders so
        JOIN store_products p ON p.id = so.product_id
        JOIN store_categories c ON c.id = p.category_id
        WHERE so.user_id = ?
        ORDER BY so.created_at DESC, so.id DESC
        """,
        (int(user_id),),
    )
    return [dict(r) for r in await cur.fetchall()]
