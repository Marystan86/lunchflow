import aiosqlite
from urllib.parse import urlparse
from fastapi import Body, HTTPException, Request

def _clamp_rating(v):
    try:
        rv = float(v)
    except Exception:
        return 0.0
    if rv < 0.0: rv = 0.0
    if rv > 5.0: rv = 5.0
    return round(rv, 2)

def _validate_time_field(t):
    """Ожидаем 'HH:MM' или пусто. Возвращаем None или строку."""
    if not t:
        return None
    if not isinstance(t, str):
        t = str(t)
    t = t.strip()
    if not t:
        return None
    parts = t.split(":")
    if len(parts) != 2:
        return None
    try:
        hh = int(parts[0])
        mm = int(parts[1])
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"
    except Exception:
        return None
    return None


PLACEHOLDER_AVATAR = "/static/images/default_avatar.svg"

def safe_avatar_url(url):
    """Возвращаем безопасный URL для аватара: только http/https и короткая длина.
       Если невалидный - возвращаем PLACEHOLDER_AVATAR.
    """
    try:
        if not url or not isinstance(url, str):
            return PLACEHOLDER_AVATAR
        url = url.strip()
        if len(url) > 1000:
            return PLACEHOLDER_AVATAR
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return PLACEHOLDER_AVATAR
        # Дополнительно: можно ограничить домены, но пока пропускаем любые http(s)
        return url
    except Exception:
        return PLACEHOLDER_AVATAR
    


def places_router(router, DB_PATH, templates):
    @router.get("/places")
    async def places_page(request: Request):
        return templates.TemplateResponse("places.html", {"request": request})

    @router.get("/api/places")
    async def api_get_places(limit: int = 50, category: str = None):
        """Возвращает список мест. Опционально фильтр по category."""
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            if category:
                cur = await db.execute("SELECT * FROM places WHERE category = ? ORDER BY created_at DESC LIMIT ?", (category, limit))
            else:
                cur = await db.execute("SELECT * FROM places ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = await cur.fetchall()
            out = []
            for r in rows:
                out.append({
                    "id": r["id"],
                    "name": r["name"],
                    "category": r["category"],
                    "rating": float(r["rating"]) if r["rating"] is not None else 0.0,
                    "open_time": r["open_time"],
                    "close_time": r["close_time"],
                    "address": r["address"],
                    "photo": safe_avatar_url(r["photo"]) if r["photo"] else None,  # reuse safe_avatar_url helper
                    "created_by_tg_id": r["created_by_tg_id"],
                    "created_at": r["created_at"]
                })
        return {"ok": True, "places": out}


    @router.post("/api/places")
    async def api_create_place(request: Request):
        """body JSON:
        {
        "name": "Cafe",
        "category": "Кофе",
        "rating": 4.5,
        "open_time": "09:00",
        "close_time": "21:30",
        "address": "ул. Пример, 1",
        "photo": "https://...",
        "created_by_tg_id": 123456
        }
        """
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="json body required")

        name = (body.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")

        category = (body.get("category") or "").strip() or None
        rating = _clamp_rating(body.get("rating", 0.0))
        open_time = _validate_time_field(body.get("open_time"))
        close_time = _validate_time_field(body.get("close_time"))
        address = (body.get("address") or "").strip() or None
        photo = body.get("photo") or None
        if photo:
            photo = safe_avatar_url(photo)

        try:
            created_by = int(body.get("created_by_tg_id")) if body.get("created_by_tg_id") else None
        except Exception:
            created_by = None

        async with aiosqlite.connect(DB_PATH) as db:
            # <- Важно: надо получить Row-объекты, чтобы обращаться по имени колонок
            db.row_factory = aiosqlite.Row

            cur = await db.execute(
                "INSERT INTO places (name, category, rating, open_time, close_time, address, photo, created_by_tg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, category, rating, open_time, close_time, address, photo, created_by)
            )
            await db.commit()

            place_id = cur.lastrowid

            # Выборка вставленной записи - теперь fetchone() вернёт aiosqlite.Row
            cur2 = await db.execute("SELECT id, name, category, rating, open_time, close_time, address, photo, created_by_tg_id, created_at FROM places WHERE id = ?", (place_id,))
            r = await cur2.fetchone()

            if not r:
                # Нечто пошло не так - возвращаем ошибку
                raise HTTPException(status_code=500, detail="failed to fetch inserted place")

            resp = {
                "id": r["id"],
                "name": r["name"],
                "category": r["category"],
                "rating": float(r["rating"]) if r["rating"] is not None else 0.0,
                "open_time": r["open_time"],
                "close_time": r["close_time"],
                "address": r["address"],
                "photo": safe_avatar_url(r["photo"]) if r["photo"] else None,
                "created_by_tg_id": r["created_by_tg_id"],
                "created_at": r["created_at"]
            }
        return {"ok": True, "place": resp}

    @router.delete("/api/places/{place_id}")
    async def api_delete_place(place_id: int):
        """Удаляет заведение по id.
        Возвращает { ok: True } или 404 если не найдено.
        """
        async with aiosqlite.connect(DB_PATH) as db:
            # хотим обращаться по именам колонок при проверке
            db.row_factory = aiosqlite.Row

            cur = await db.execute("SELECT id FROM places WHERE id = ?", (place_id,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="place not found")

            # простое удаление; можно заменить на soft-delete, если нужно
            await db.execute("DELETE FROM places WHERE id = ?", (place_id,))
            await db.commit()

        return {"ok": True}
