import aiosqlite


async def get_by_tg_id(db: aiosqlite.Connection, tg_id: int) -> dict | None:
    cur = await db.execute("SELECT * FROM users WHERE tg_id = ? LIMIT 1", (tg_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_by_id(db: aiosqlite.Connection, user_id: int) -> dict | None:
    cur = await db.execute("SELECT * FROM users WHERE id = ? LIMIT 1", (user_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def ensure_dev_user(
    db: aiosqlite.Connection,
    *,
    user_id: int,
    full_name: str,
    role: str = "member",
) -> dict:
    existing = await get_by_id(db, int(user_id))
    if existing is not None:
        return existing

    tg_id = 970000000 + int(user_id)
    while await get_by_tg_id(db, tg_id) is not None:
        tg_id += 1

    await db.execute(
        """
        INSERT INTO users (
            id, tg_id, source, tg_username, full_name, role, is_admin, status, created_at, updated_at
        ) VALUES (?, ?, 'real', ?, ?, ?, 0, 'active', datetime('now'), datetime('now'))
        """,
        (
            int(user_id),
            int(tg_id),
            f"dev_seed_{int(user_id)}",
            full_name,
            role,
        ),
    )
    created = await get_by_id(db, int(user_id))
    if created is None:
        raise RuntimeError("failed to create dev user")
    return created


async def create_user_from_tg(
    db: aiosqlite.Connection,
    tg_user_dict: dict,
    role: str,
    status: str,
) -> dict:
    full_name = " ".join(
        part for part in [tg_user_dict.get("first_name", ""), tg_user_dict.get("last_name", "")] if part
    ).strip()

    cur = await db.execute(
        """
        INSERT INTO users (
            tg_id, tg_username, full_name, photo_url, role, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            int(tg_user_dict["id"]),
            tg_user_dict.get("username"),
            full_name,
            tg_user_dict.get("photo_url"),
            role,
            status,
        ),
    )
    await db.commit()
    return await get_by_id(db, int(cur.lastrowid))


async def update_user_profile(db: aiosqlite.Connection, user_id: int, patch_dict: dict) -> dict | None:
    allowed = {
        "tg_username",
        "full_name",
        "photo_url",
        "city",
        "company",
        "position",
        "industry",
        "annual_revenue",
        "employee_count",
        "core_competencies",
        "goal_2025",
        "club_request",
        "hobbies",
        "help_offer",
        "bio",
        "help_tags",
        "need_tags",
        "contacts",
        "visibility",
        "role",
        "status",
    }
    fields = []
    params = []
    for key, value in patch_dict.items():
        if key not in allowed:
            continue
        fields.append(f"{key} = ?")
        params.append(value)

    if not fields:
        return await get_by_id(db, user_id)

    params.append(user_id)
    query = f"UPDATE users SET {', '.join(fields)}, updated_at = datetime('now') WHERE id = ?"
    await db.execute(query, tuple(params))
    await db.commit()
    return await get_by_id(db, user_id)


async def list_members(
    db: aiosqlite.Connection,
    query: str | None = None,
    city: str | None = None,
    tags: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    select_columns = """
        id, tg_id, tg_username, full_name, photo_url, role, status,
        city, company, position, company_name, industry, annual_revenue,
        employee_count, core_competencies, goal_2025, club_request, hobbies,
        help_offer, help_tags, need_tags, contacts, visibility, created_at, updated_at
    """
    where = ["status = 'active'"]
    params: list = []

    if query:
        where.append("(full_name LIKE ? OR tg_username LIKE ? OR company LIKE ? OR position LIKE ?)")
        like_query = f"%{query}%"
        params.extend([like_query, like_query, like_query, like_query])

    if city:
        where.append("city = ?")
        params.append(city)

    if tags:
        like_tag = f"%{tags}%"
        where.append("(help_tags LIKE ? OR need_tags LIKE ?)")
        params.extend([like_tag, like_tag])

    sql = f"""
        SELECT {select_columns} FROM users
        WHERE {' AND '.join(where)}
        ORDER BY updated_at DESC, id DESC
        LIMIT ? OFFSET ?
    """
    params.extend([int(limit), int(offset)])

    cur = await db.execute(sql, tuple(params))
    rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def list_public_members(
    db: aiosqlite.Connection,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    select_columns = """
        id, tg_id, tg_username, full_name, photo_url, role, status,
        city, company, position, company_name, industry, annual_revenue,
        employee_count, core_competencies, goal_2025, club_request, hobbies,
        help_offer, help_tags, need_tags, contacts, visibility, created_at, updated_at
    """
    cur = await db.execute(
        """
        SELECT
        """
        + select_columns
        + """
        FROM users
        WHERE status = 'active' AND source = 'sample'
        ORDER BY updated_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (int(limit), int(offset)),
    )
    rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def list_badges_preview_for_users(
    db: aiosqlite.Connection,
    user_ids: list[int],
    limit_per_user: int = 3,
) -> dict[int, list[dict]]:
    if not user_ids:
        return {}

    placeholders = ",".join("?" for _ in user_ids)
    cur = await db.execute(
        f"""
        SELECT
            ub.user_id,
            b.code,
            b.title,
            b.icon,
            b.badge_type,
            ub.earned_at
        FROM user_badges ub
        JOIN badges b ON b.id = ub.badge_id
        WHERE ub.user_id IN ({placeholders}) AND b.is_active = 1
        ORDER BY ub.user_id ASC, ub.earned_at DESC, ub.badge_id DESC
        """,
        tuple(int(uid) for uid in user_ids),
    )
    rows = await cur.fetchall()

    grouped: dict[int, list[dict]] = {}
    for row in rows:
        user_id = int(row["user_id"])
        bucket = grouped.setdefault(user_id, [])
        if len(bucket) >= limit_per_user:
            continue
        bucket.append(
            {
                "code": row["code"],
                "title": row["title"],
                "icon": row["icon"],
                "badge_type": row["badge_type"],
            }
        )

    return grouped
