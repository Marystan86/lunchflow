# app/telegram_utils.py

import json
import asyncio
import aiohttp 
import logging
import aiosqlite
import html as _html

from routes import DB_PATH
from app.config import BOT_TOKEN

import socket

# helper - try to use shared session if available
async def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None, sess: aiohttp.ClientSession = None):
    if not BOT_TOKEN:
        logging.warning("send_telegram_message: BOT_TOKEN not set")
        return None

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    safe_text = _html.escape(text)
    payload = {"chat_id": chat_id, "text": safe_text, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

    created_session = False
    try:
        # prefer passed session, then global app.session if available, else create one forced to IPv4
        if sess is None:
            # try to get global session created in main.lifespan
            try:
                from fastapi import Request
                # lazy import to avoid circular; assume main set app.state.http_session
                from main import app as main_app
                sess = getattr(main_app.state, "http_session", None)
            except Exception:
                sess = None

        if sess is None:
            sess = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=50, family=socket.AF_INET))
            created_session = True

        MAX_ATTEMPTS = 3
        TIMEOUT = 15  # seconds
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with sess.post(url, json=payload, timeout=TIMEOUT) as resp:
                    try:
                        j = await resp.json()
                    except Exception:
                        j = {"ok": False, "http_status": resp.status}
                    if not j.get("ok"):
                        logging.warning("telegram send failed (chat=%s) resp=%s", chat_id, j)
                    return j
            except asyncio.TimeoutError:
                logging.warning("send_telegram_message timeout for chat_id=%s attempt=%d", chat_id, attempt)
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(1.0 * attempt)
                    continue
                return None
            except aiohttp.ClientError as e:
                logging.warning("send_telegram_message client error for chat_id=%s: %s", chat_id, e)
                return None
    finally:
        if created_session and sess is not None:
            await sess.close()


async def answer_callback_query(callback_query_id: str, text: str = None, show_alert: bool = False):
    if not BOT_TOKEN:
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id, "show_alert": bool(show_alert)}
    if text:
        payload["text"] = text
    try:
        async with aiohttp.ClientSession() as sess:
            await sess.post(url, json=payload, timeout=5)
    except Exception:
        logging.exception("answerCallbackQuery failed")


        
async def edit_message_reply_markup(chat_id: int = None, message_id: int = None, inline_message_id: str = None, reply_markup: dict = None):
    if not BOT_TOKEN:
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup"
    payload = {}
    if chat_id is not None and message_id is not None:
        payload["chat_id"] = chat_id
        payload["message_id"] = message_id
    elif inline_message_id is not None:
        payload["inline_message_id"] = inline_message_id
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    try:
        async with aiohttp.ClientSession() as sess:
            await sess.post(url, json=payload, timeout=5)
    except Exception:
        logging.exception("editMessageReplyMarkup failed")


async def edit_message_text(chat_id: int = None, message_id: int = None, inline_message_id: str = None, text: str = None):
    if not BOT_TOKEN:
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {"parse_mode": "HTML"}
    if chat_id is not None and message_id is not None:
        payload["chat_id"] = chat_id
        payload["message_id"] = message_id
    elif inline_message_id is not None:
        payload["inline_message_id"] = inline_message_id
    payload["text"] = text or ""
    try:
        async with aiohttp.ClientSession() as sess:
            await sess.post(url, json=payload, timeout=5)
    except Exception:
        logging.exception("editMessageText failed")


# helper - формирует телеграм inline keyboard (Yes/No)
# def telegram_survey_keyboard(invite_id):
#     return {
#         "inline_keyboard": [
#             [{"text":"Да","callback_data": f"survey:{invite_id}:yes"}],
#             [{"text":"Нет","callback_data": f"survey:{invite_id}:no"}]
#         ]
#     }


async def dispatch_surveys_once():
    """Ищет accepted invites с ответом >=10 секунд назад и survey_sent=0, создает notifications и отправляет telegram."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # cur = await db.execute("""
        #     SELECT i.id, i.from_user_id, i.to_user_id, i.place_name, i.responded_at, i.meal_type,
        #            fu.tg_id AS from_tg, tu.tg_id AS to_tg, fu.name AS from_name, tu.name AS to_name
        #     FROM invites i
        #     JOIN users fu ON fu.id = i.from_user_id
        #     JOIN users tu ON tu.id = i.to_user_id
        #     WHERE i.status = 'accepted' AND IFNULL(i.survey_sent,0) = 0
        #       AND strftime('%s', replace(replace(i.responded_at,'T',' '),'Z','')) <= strftime('%s', 'now', '-10 seconds')
        # """)
        cur = await db.execute("""
            SELECT i.id, i.from_user_id, i.to_user_id, i.place_name, i.responded_at, i.meal_type,
                fu.tg_id AS from_tg, tu.tg_id AS to_tg, fu.name AS from_name, tu.name AS to_name
            FROM invites i
            JOIN users fu ON fu.id = i.from_user_id
            JOIN users tu ON tu.id = i.to_user_id
            WHERE i.status = 'accepted' AND IFNULL(i.survey_sent,0) = 0
            AND strftime('%s', replace(replace(i.responded_at,'T',' '),'Z','')) <= strftime('%s', 'now', '-1 hour')
        """)
        rows = await cur.fetchall()
        if not rows:
            return

        for row in rows:
            r = dict(row)  # безопасный словарь
            invite_id = r.get("id")

            # попытка пометить invite как отправленный (race-safe)
            try:
                await db.execute("UPDATE invites SET survey_sent = 1 WHERE id = ? AND IFNULL(survey_sent,0) = 0", (invite_id,))
                await db.commit()
                cur_changes = await db.execute("SELECT changes() AS cnt")
                ch = await cur_changes.fetchone()
                if not ch or int(ch["cnt"]) == 0:
                    continue
            except Exception:
                logging.exception("failed to mark survey_sent for invite %s", invite_id)
                continue

            # payload для уведомления в мини-аппе
            payload_from = {
                "invite_id": invite_id,
                "place_name": r.get("place_name"),
                "partner_name": r.get("to_name"),
                "partner_tg": r.get("to_tg"),
                "role": "initiator"
            }
            payload_to = {
                "invite_id": invite_id,
                "place_name": r.get("place_name"),
                "partner_name": r.get("from_name"),
                "partner_tg": r.get("from_tg"),
                "role": "responder"
            }

            # формируем дружелюбные тексты с запасными значениями
            place = r.get("place_name") or ""
            place_text = f' в "{place}"' if place else ""
            meal_type = (r.get("meal_type") or "встречу").strip()
            from_display = r.get("from_name") or (("@%s" % r.get("from_tg")) if r.get("from_tg") else "пользователь")
            to_display = r.get("to_name") or (("@%s" % r.get("to_tg")) if r.get("to_tg") else "пользователь")

            text_for_from = f'Сходили ли вы с "{to_display}" на {meal_type}{place_text}?Зайдите в мини-апп и ответься пожалуйста))'
            text_for_to   = f'Сходили ли вы с "{from_display}" на {meal_type}{place_text}?\nЗайдите в мини-апп и ответься пожалуйста))'

            # вставляем notifications в БД (initiator и responder)
            try:
                await db.execute(
                    "INSERT INTO notifications (user_id, type, payload, read, created_at) VALUES (?, ?, ?, 0, datetime('now'))",
                    (r.get("from_user_id"), "survey", json.dumps(payload_from, ensure_ascii=False))
                )
                await db.execute(
                    "INSERT INTO notifications (user_id, type, payload, read, created_at) VALUES (?, ?, ?, 0, datetime('now'))",
                    (r.get("to_user_id"), "survey", json.dumps(payload_to, ensure_ascii=False))
                )
                await db.commit()
            except Exception:
                logging.exception("failed to insert notifications for invite %s", invite_id)

            # best-effort: отправляем telegram (текст тем, кто должен ответить)
            try:
                if r.get("from_tg"):
                    await send_telegram_message(r.get("from_tg"), text_for_from)
                if r.get("to_tg"):
                    await send_telegram_message(r.get("to_tg"), text_for_to)
            except Exception:
                logging.exception("survey send telegram failed for invite %s", invite_id)