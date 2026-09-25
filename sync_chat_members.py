#!/usr/bin/env python3
"""
One-off script to import all members of a Telegram chat into local DB.
Requires: Pyrogram (async client) and valid Telegram API credentials.

Usage:
1) Fill API_ID, API_HASH and CHAT_ID below.
2) Run: python sync_chat_members.py
"""
from __future__ import annotations

import asyncio
import logging

from pyrogram import Client

from db.base import async_session
from services import users as users_service

# Hardcode values for a one-off run.
# For supergroups with topics, prefer the parent chat username or the real group ID,
# not a forum topic/thread id.
API_ID = 35720595
API_HASH = "c911bbd51361466d45f5de40c4401096"
CHAT_ID = -1003730057446  # e.g. "@CreamNemesis" or "-1001234567890"

logger = logging.getLogger("sync_chat_members")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def _print_chat_candidates(app: Client) -> None:
    logger.warning("Trying to detect valid chat peers from your dialogs...")
    async for dialog in app.get_dialogs():
        chat = dialog.chat
        title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or ""
        username = getattr(chat, "username", None)
        if title:
            print(f"TITLE={title!r} ID={chat.id} USERNAME={username}")


async def main() -> None:
    if API_HASH == "PASTE_YOUR_API_HASH_HERE":
        raise ValueError(
            "Подставь реальные API_ID / API_HASH / CHAT_ID в constants в начале файла."
        )

    logger.info("Starting Pyrogram client...")
    count = 0

    app = Client("sync_members_oneoff", api_id=API_ID, api_hash=API_HASH)

    async with app:
        logger.info("Connected to Telegram — iterating members of %s", CHAT_ID)
        try:
            async for member in app.get_chat_members(CHAT_ID):
                user = member.user
                if user is None:
                    continue
                if getattr(user, "is_bot", False):
                    continue

                try:
                    async with async_session() as session:
                        await users_service.get_or_create_user(
                            session,
                            tg_id=user.id,
                            username=user.username,
                        )
                        await session.commit()
                    count += 1
                    if count % 50 == 0:
                        logger.info("Imported %d members so far...", count)
                except Exception:
                    logger.exception(
                        "Failed to import user %s (%s)",
                        getattr(user, "id", None),
                        getattr(user, "username", None),
                    )
        except ValueError as exc:
            logger.error(
                "Peer id invalid: %s. Use parent chat username or real chat ID, not a forum topic id. Example: '@your_group_username' or '-1001234567890'.",
                exc,
            )
            await _print_chat_candidates(app)
            raise

    logger.info("Import finished. Импортировано %d участников.", count)


if __name__ == "__main__":
    asyncio.run(main())
