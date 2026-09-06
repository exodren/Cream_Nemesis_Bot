#!/usr/bin/env python3
"""
One-off script to import all members of a Telegram chat into local DB.
Requires: Pyrogram (async client), access to API_ID/API_HASH and user that is a member of the chat.

Run: python sync_chat_members.py

The script will prompt for missing values.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from pyrogram import Client

from db.base import async_session
from services import users as users_service

logger = logging.getLogger("sync_chat_members")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _get_env_or_input(name: str, cast: Optional[type] = None) -> str:
    val = os.getenv(name)
    if val:
        return val
    prompt = f"{name}: "
    raw = input(prompt).strip()
    return raw


async def main() -> None:
    api_id = _get_env_or_input("API_ID")
    api_hash = _get_env_or_input("API_HASH")
    chat_id = _get_env_or_input("CHAT_ID")

    # Basic validation / casts
    try:
        api_id = int(api_id)
    except Exception:
        logger.error("API_ID must be an integer")
        return

    if not api_hash:
        logger.error("API_HASH is required")
        return

    # chat_id can be numeric or @username
    # No cast here

    logger.info("Starting Pyrogram client...")
    count = 0

    # Use a short session name — no persistent session data required for one-off run.
    app = Client("sync_members_oneoff", api_id=api_id, api_hash=api_hash)

    async with app:
        logger.info("Connected to Telegram — iterating members of %s", chat_id)
        # Pyrogram provides an async iterator for get_chat_members
        async for member in app.get_chat_members(chat_id):
            user = member.user
            if user is None:
                continue
            if getattr(user, "is_bot", False):
                continue

            try:
                async with async_session() as session:
                    # Use existing service which performs get_or_create semantics
                    await users_service.get_or_create_user(
                        session,
                        tg_id=user.id,
                        username=user.username,
                    )
                    await session.commit()
                count += 1
                if count % 50 == 0:
                    logger.info("Imported %d members so far...", count)
            except Exception as exc:  # pragma: no cover - one-off script
                logger.exception("Failed to import user %s (%s): %s", getattr(user, 'id', None), getattr(user, 'username', None), exc)

    logger.info("Import finished. Импортировано %d участников.", count)


if __name__ == "__main__":
    asyncio.run(main())
