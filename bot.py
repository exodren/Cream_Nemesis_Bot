from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import text

from config import get_settings
from db.base import engine, init_db
from handlers.admin import router as admin_router
from handlers.common import router as common_router
from handlers.matchmaking import router as matchmaking_router
from handlers.menu import router as menu_router
from handlers.results import router as results_router
from handlers.start import router as start_router
from handlers.tova.registration import router as registration_router
from handlers.tova.stats import router as stats_router
from logging_setup import setup_logging
from middlewares.db import DbSessionMiddleware


async def _log_db_mode() -> None:
    async with engine.connect() as conn:
        mode = (await conn.execute(text("PRAGMA journal_mode;"))).scalar()
        logging.info("SQLite journal_mode=%s", mode)


async def main() -> None:
    log_path = setup_logging()

    settings = get_settings()
    token = settings.require_token()
    await init_db()
    await _log_db_mode()

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DbSessionMiddleware())

    # Order matters: specific TOVA routers before generic menu catch-alls
    dp.include_router(start_router)
    dp.include_router(registration_router)
    dp.include_router(matchmaking_router)
    dp.include_router(results_router)
    dp.include_router(stats_router)
    dp.include_router(admin_router)
    dp.include_router(common_router)
    dp.include_router(menu_router)

    me = await bot.get_me()
    logging.info(
        "Cream Nemesis Bot @%s starting (polling). Admins: %s | log=%s",
        me.username,
        settings.admin_ids,
        log_path,
    )
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by KeyboardInterrupt")
        sys.exit(0)
