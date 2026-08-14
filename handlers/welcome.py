from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters.chat_member_updated import JOIN_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated

from texts import REGULATION

router = Router(name="welcome")
logger = logging.getLogger(__name__)


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_joined(event: ChatMemberUpdated) -> None:
    user = event.new_chat_member.user
    if user.is_bot:
        return
    if event.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return

    mention = user.mention_html()
    text = (
        f"{mention}, добро пожаловать в Cream Nemesis!\n\n"
        f"{REGULATION}"
    )
    try:
        await event.bot.send_message(event.chat.id, text)
    except Exception:
        logger.exception(
            "Welcome message failed chat=%s user=%s",
            event.chat.id,
            user.id,
        )
    else:
        logger.info("Welcomed user=%s in chat=%s", user.id, event.chat.id)
