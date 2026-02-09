# app/invites.py

import json
import logging
import aiosqlite
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

from routes import DB_PATH
from app.telegram_utils import send_telegram_message

async def handle_invite_response(invite_id: int, responder_tg: int, action: str):
    if action not in ("accept", "decline"):
        raise ValueError("invalid action")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT i.id, i.status, i.from_user_id, i.to_user_id, i.place_name, i.time_iso, i.meal_type, fu.tg_id AS from_tg, tu.tg_id AS to_tg, fu.name AS from_name "
            "FROM invites i JOIN users fu ON fu.id = i.from_user_id JOIN users tu ON tu.id = i.to_user_id WHERE i.id = ?",
            (invite_id,)
        )
        inv = await cur.fetchone()
        if not inv:
            return {"ok": False, "error": "invite not found"}
       
        # --- безопасная проверка: responder имеет право отвечать на это приглашение ---
        try:
            stored_to_tg = inv["to_tg"]
        except Exception:
            stored_to_tg = None

        # Если в БД нет to_tg или он не совпадает с приславшим запрос - отказ
        try:
            if stored_to_tg is None or int(stored_to_tg) != int(responder_tg):
                return {"ok": False, "error": "not authorized"}
        except Exception:
            return {"ok": False, "error": "not authorized"}

        if inv["status"] != "pending":
            return {"ok": False, "error": f"already {inv['status']}"}

        new_status = "accepted" if action == "accept" else "declined"

        # найдем responder_user_id
        cur = await db.execute("SELECT id, name, username, tg_id FROM users WHERE tg_id = ?", (responder_tg,))
        r = await cur.fetchone()
        responder_user_id = r["id"] if r else None
        responder_name = None
        responder_username = None
        if r:
            responder_name = r["name"] or None
            responder_username = (r["username"] or None)

        await db.execute(
            "UPDATE invites SET status = ?, responder_user_id = ?, responded_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (new_status, responder_user_id, invite_id))
        await db.commit()

        # --- подготовка читаемого времени (Asia/Almaty) ---
        time_readable = ""
        raw_time = inv["time_iso"]
        if raw_time:
            try:
                t = raw_time
                if t.endswith("Z"):
                    t = t[:-1]
                try:
                    dt = datetime.fromisoformat(t)
                except Exception:
                    dt = datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                try:
                    almaty = ZoneInfo("Asia/Almaty")
                    dt_local = dt.astimezone(almaty)
                except Exception:
                    dt_local = dt.astimezone(timezone.utc)
                ru_months = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"]
                hhmm = dt_local.strftime("%H:%M")
                day = dt_local.day
                month = ru_months[dt_local.month - 1]
                time_readable = f"{hhmm} {day} {month}"
            except Exception:
                logging.exception("time parse failed")

        # --- Формирование текста уведомления для инициатора ---
        place_text = f' в "{inv["place_name"]}"' if inv["place_name"] else ""
        meal_type = inv["meal_type"] or "встречу"

        status_text = "принято" if new_status == "accepted" else "отказано"
        emojis = "🥳🥳🥳" if new_status == "accepted" else "😭😭😭"

        # responder_display = responder_name or ("@" + str(responder_tg)) if responder_tg else "пользователь"
        if responder_name:
            responder_display = responder_name
        elif responder_username:
            responder_display = "@" + str(responder_username)
        elif responder_tg:
            responder_display = "@" + str(responder_tg)
        else:
            responder_display = "пользователь"

        when_part = f"в {time_readable}" if time_readable else (f"в {inv['time_iso']}" if inv["time_iso"] else "")

        # При принятии добавляем отдельную строку с username (если есть) - как просил
        contact_line = ""
        if new_status == "accepted":
            if responder_username:
                contact_line = f"\n\nСвяжись с @{responder_username}"
            elif responder_tg:
                contact_line = f"\n\nСвяжись с @{responder_tg}"

        telegram_text = f'Ваше приглашение{place_text} с {responder_display} на {meal_type} {when_part} было {status_text} {emojis}{contact_line}'

        # Отправим Telegram (best-effort)
        try:
            await send_telegram_message(inv["from_tg"], telegram_text)
        except Exception:
            logging.exception("failed to send telegram notify to initiator")

        # --- Создадим запись в notifications для мини-аппа инициатора ---
        notif_payload = {
            "invite_id": invite_id,
            "place_name": inv["place_name"],
            "meal_type": meal_type,
            "time_readable": time_readable,
            "responder_name": responder_display,
            "status": new_status
        }
        try:
            await db.execute(
                "INSERT INTO notifications (user_id, type, payload, read, created_at) VALUES (?, ?, ?, 0, datetime('now'))",
                (inv["from_user_id"], "invite_response", json.dumps(notif_payload, ensure_ascii=False))
            )
            await db.commit()
        except Exception:
            logging.exception("failed to insert notification")

        return {"ok": True, "invite_id": invite_id, "status": new_status}

