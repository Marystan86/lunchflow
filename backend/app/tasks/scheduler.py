import asyncio
import logging

import aiohttp
import aiosqlite

from backend.app.settings import settings
from backend.app.tasks.jobs import dispatch_surveys_once


logger = logging.getLogger(__name__)


async def survey_scheduler_loop(
    stop_event: asyncio.Event,
    session: aiohttp.ClientSession,
    interval_seconds: int | None = None,
) -> None:
    poll_interval = max(30, interval_seconds or settings.survey_interval_seconds)
    logger.info("New survey scheduler started with interval=%ss", poll_interval)
    try:
        while not stop_event.is_set():
            try:
                async with aiosqlite.connect(settings.db_path) as db:
                    db.row_factory = aiosqlite.Row
                    processed = await dispatch_surveys_once(db, session)
                    if processed:
                        logger.info("New survey scheduler processed invites: %s", processed)
            except Exception:
                logger.exception("New survey scheduler iteration failed")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=float(poll_interval))
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        logger.info("New survey scheduler cancelled")
        raise
