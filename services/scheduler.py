from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import get_settings
from db.base import async_session
from services import lpl_roster as lpl_service
from services import moderation as mod

logger = logging.getLogger(__name__)

# Asia/Almaty (UTC+5) — matches operators' local time in project notes.
_TZ = ZoneInfo("Asia/Almaty")

scheduler = AsyncIOScheduler(timezone=_TZ)


async def job_expire_warnings() -> None:
    async with async_session() as session:
        try:
            expired = await mod.expire_old_warnings(session)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Warn expiry job failed")
            return
    if expired:
        logger.info("Expired %s warning(s) older than %s days", expired, mod.WARN_TTL_DAYS)
    else:
        logger.debug("Warn expiry job: nothing to expire")


async def job_lpl_auto_tag(bot: Bot) -> None:
    settings = get_settings()
    chat_id = settings.main_chat_id
    if not chat_id:
        logger.warning("LPL auto-tag skipped: MAIN_CHAT_ID is empty")
        return

    async with async_session() as session:
        try:
            members = await lpl_service.list_roster(session)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("LPL auto-tag: failed to load roster")
            return

    if not members:
        logger.info("LPL auto-tag skipped: roster empty")
        return

    text = lpl_service.build_lpl_reminder_html(members)
    try:
        await bot.send_message(chat_id, text, disable_web_page_preview=True)
        logger.info("LPL auto-tag sent to chat=%s members=%s", chat_id, len(members))
    except Exception:
        logger.exception("LPL auto-tag send failed chat=%s", chat_id)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Register cron jobs. Call once before polling; shutdown on exit."""
    if scheduler.running:
        return scheduler

    scheduler.add_job(
        job_expire_warnings,
        CronTrigger(hour=3, minute=0, timezone=_TZ),
        id="expire_warnings",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    for hour in (12, 16, 20):
        scheduler.add_job(
            job_lpl_auto_tag,
            CronTrigger(hour=hour, minute=0, timezone=_TZ),
            kwargs={"bot": bot},
            id=f"lpl_tag_{hour:02d}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    scheduler.start()
    logger.info(
        "APScheduler started (tz=%s): warn expiry 03:00; LPL tags 12:00/16:00/20:00",
        _TZ,
    )
    return scheduler


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
