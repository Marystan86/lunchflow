import json
import logging

import aiohttp
import aiosqlite

from backend.app.repositories import legacy_invites_repo
from backend.app.services import tg_service


logger = logging.getLogger(__name__)


def _display_name(name: str, tg_id: int | None) -> str:
    if name:
        return name
    if tg_id:
        return f"@{tg_id}"
    return "пользователь"


async def dispatch_surveys_once(db: aiosqlite.Connection, session: aiohttp.ClientSession) -> int:
    await legacy_invites_repo.ensure_notifications_table(db)
    invites = await legacy_invites_repo.get_invites_need_survey(db)
    if not invites:
        await db.commit()
        return 0

    processed = 0
    for invite in invites:
        invite_id = int(invite["id"])
        locked = await legacy_invites_repo.mark_survey_sent(db, invite_id)
        await db.commit()
        if not locked:
            continue

        place = (invite.get("place_name") or "").strip()
        meal_type = (invite.get("meal_type") or "встречу").strip()
        place_text = f' в "{place}"' if place else ""

        from_name = _display_name(invite.get("from_name", ""), invite.get("from_tg"))
        to_name = _display_name(invite.get("to_name", ""), invite.get("to_tg"))

        payload_from = json.dumps(
            {
                "invite_id": invite_id,
                "place_name": invite.get("place_name"),
                "partner_name": to_name,
                "partner_tg": invite.get("to_tg"),
                "role": "initiator",
            },
            ensure_ascii=False,
        )
        payload_to = json.dumps(
            {
                "invite_id": invite_id,
                "place_name": invite.get("place_name"),
                "partner_name": from_name,
                "partner_tg": invite.get("from_tg"),
                "role": "responder",
            },
            ensure_ascii=False,
        )

        msg_for_from = f'Сходили ли вы с "{to_name}" на {meal_type}{place_text}? Зайдите в мини-апп и ответьте.'
        msg_for_to = f'Сходили ли вы с "{from_name}" на {meal_type}{place_text}? Зайдите в мини-апп и ответьте.'

        await legacy_invites_repo.insert_notification(
            db,
            user_id=int(invite["from_user_id"]),
            title="survey",
            body=msg_for_from,
            payload_json=payload_from,
        )
        await legacy_invites_repo.insert_notification(
            db,
            user_id=int(invite["to_user_id"]),
            title="survey",
            body=msg_for_to,
            payload_json=payload_to,
        )
        await db.commit()

        try:
            if invite.get("from_tg"):
                await tg_service.send_telegram_message(session, int(invite["from_tg"]), msg_for_from)
            if invite.get("to_tg"):
                await tg_service.send_telegram_message(session, int(invite["to_tg"]), msg_for_to)
        except Exception:
            logger.exception("Failed to send survey telegram messages for invite_id=%s", invite_id)

        processed += 1

    return processed
