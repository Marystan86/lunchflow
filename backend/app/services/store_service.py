from fastapi import HTTPException

from backend.app.repositories import points_repo, store_repo, users_repo
from backend.app.services import points_service


def _to_ui_category(row: dict) -> dict:
    return {"id": int(row["id"]), "slug": row["slug"], "title": row["title"]}


def _stock_text(stock_limit: int | None, paid_count: int) -> str:
    if stock_limit is None:
        return "Без ограничений"
    current = max(int(stock_limit) - int(paid_count), 0)
    return f"В наличии: {current}"


def _to_ui_product(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "title": row["title"],
        "description": row.get("description") or "",
        "costPoints": int(row["price_points"]),
        "category": row.get("category_title") or "",
        "category_slug": row.get("category_slug") or "",
        "stock_limit": row.get("stock_limit"),
        "stock_text": _stock_text(row.get("stock_limit"), int(row.get("paid_count") or 0)),
        "isRepeatable": bool(row.get("is_repeatable")),
        "perUserLimit": row.get("per_user_limit"),
        "imageKey": row.get("image_key"),
    }


def _level_from_points(points: int) -> str:
    if points >= 300:
        return "Партнёр"
    if points >= 120:
        return "Активный"
    return "Старт"


async def list_categories(db) -> list[dict]:
    rows = await store_repo.list_categories(db)
    return [_to_ui_category(r) for r in rows]


async def list_products(db, *, category_slug: str | None = None) -> list[dict]:
    rows = await store_repo.list_products(db, category_slug=category_slug, only_active=True)
    return [_to_ui_product(r) for r in rows]


async def get_user_store_summary(db, *, user_id: int) -> dict:
    user = await users_repo.get_by_id(db, int(user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    balance = await points_repo.get_balance(db, int(user_id))
    orders = await store_repo.list_user_orders(db, int(user_id))
    return {
        "points": int(balance),
        "level": _level_from_points(int(balance)),
        "purchases": [
            {
                "id": int(o["id"]),
                "itemId": int(o["product_id"]),
                "title": o.get("product_title") or "",
                "costPoints": int(o.get("total_points") or 0),
                "redeemedAt": o.get("created_at"),
                "status": o.get("status"),
            }
            for o in orders
        ],
    }


async def create_order(db, *, user_id: int, product_id: int, qty: int = 1) -> dict:
    if int(qty) <= 0:
        raise HTTPException(status_code=400, detail="qty must be > 0")
    product = await store_repo.get_product_by_id(db, int(product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    if int(product.get("is_active") or 0) != 1:
        raise HTTPException(status_code=400, detail="product is inactive")

    is_repeatable = int(product.get("is_repeatable") or 0) == 1
    if not is_repeatable:
        existing = await store_repo.get_nonrepeat_paid_order(db, int(user_id), int(product_id))
        if existing is not None:
            return {
                "ok": True,
                "order_id": int(existing["id"]),
                "status": existing["status"],
                "points_spent": int(existing["total_points"]),
                "already_owned": True,
            }

    per_user_limit = product.get("per_user_limit")
    if per_user_limit is not None:
        paid_count = await store_repo.count_user_product_paid_orders(db, int(user_id), int(product_id))
        if paid_count + int(qty) > int(per_user_limit):
            raise HTTPException(status_code=400, detail="per_user_limit exceeded")

    stock_limit = product.get("stock_limit")
    if stock_limit is not None:
        paid_count_total = int(product.get("paid_count") or 0)
        if paid_count_total + int(qty) > int(stock_limit):
            raise HTTPException(status_code=400, detail="stock_limit exceeded")

    total_points = int(product["price_points"]) * int(qty)
    balance = await points_repo.get_balance(db, int(user_id))
    if int(balance) < int(total_points):
        return {"ok": False, "reason": "not_enough_points", "required": total_points, "points": int(balance)}

    order = await store_repo.create_order(
        db,
        user_id=int(user_id),
        product_id=int(product_id),
        qty=int(qty),
        total_points=int(total_points),
        status="paid",
        is_repeatable_snapshot=1 if is_repeatable else 0,
    )
    exists = await points_repo.has_ledger_entry(
        db,
        user_id=int(user_id),
        reason_type="store_purchase",
        entity_type="store_order",
        entity_id=int(order["id"]),
    )
    if not exists:
        await points_service.add_points(
            db,
            user_id=int(user_id),
            amount=-int(total_points),
            reason_type="store_purchase",
            entity_type="store_order",
            entity_id=int(order["id"]),
            meta={"product_id": int(product_id), "qty": int(qty)},
        )

    return {
        "ok": True,
        "order_id": int(order["id"]),
        "status": order["status"],
        "points_spent": int(total_points),
        "already_owned": False,
    }
