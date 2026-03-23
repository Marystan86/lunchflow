import asyncio
import html
import json
import logging
from typing import Any

import aiohttp

from backend.app.settings import settings


logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 3


def _bot_url(method: str) -> str:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not configured")
    return f"https://api.telegram.org/bot{settings.bot_token}/{method}"


async def _post_with_retry(
    session: aiohttp.ClientSession,
    method: str,
    payload: dict[str, Any],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any] | None:
    url = _bot_url(method)
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with session.post(url, json=payload, timeout=timeout) as response:
                try:
                    data = await response.json()
                except Exception:
                    raw_text = await response.text()
                    logger.warning("Telegram %s non-JSON response: %s", method, raw_text)
                    data = {"ok": False, "status": response.status, "raw": raw_text}

                if not data.get("ok"):
                    logger.warning("Telegram %s failed on attempt %d: %s", method, attempt, data)
                return data
        except asyncio.TimeoutError:
            logger.warning("Telegram %s timeout on attempt %d", method, attempt)
        except aiohttp.ClientError:
            logger.exception("Telegram %s network error on attempt %d", method, attempt)
        except Exception:
            logger.exception("Telegram %s unexpected error on attempt %d", method, attempt)

        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(attempt)

    return None


async def send_telegram_message(
    session: aiohttp.ClientSession,
    chat_id: int,
    text: str,
    reply_markup: dict[str, Any] | None = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> dict[str, Any] | None:
    safe_text = html.escape(text or "") if parse_mode == "HTML" else (text or "")
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": safe_text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return await _post_with_retry(session, "sendMessage", payload)


async def answer_callback_query(
    session: aiohttp.ClientSession,
    callback_query_id: str,
    text: str | None = None,
    show_alert: bool = False,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": bool(show_alert)}
    if text:
        payload["text"] = text
    return await _post_with_retry(session, "answerCallbackQuery", payload, timeout_seconds=5)


async def edit_message_text(
    session: aiohttp.ClientSession,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: dict[str, Any] | None = None,
    parse_mode: str = "HTML",
) -> dict[str, Any] | None:
    safe_text = html.escape(text or "") if parse_mode == "HTML" else (text or "")
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": safe_text,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return await _post_with_retry(session, "editMessageText", payload)


async def edit_message_reply_markup(
    session: aiohttp.ClientSession,
    chat_id: int,
    message_id: int,
    reply_markup: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    return await _post_with_retry(session, "editMessageReplyMarkup", payload)
