from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeChatMember,
    BotCommandScopeDefault,
)

from config import get_settings

logger = logging.getLogger(__name__)

USER_COMMANDS = [
    BotCommand(command="start", description="Запуск бота"),
    BotCommand(command="help", description="Связь с Администраторами / Справка"),
    BotCommand(command="go_tova", description="Найти матч TOVA"),
    BotCommand(command="result_tova", description="Внести результат матча"),
]

ADMIN_COMMANDS = USER_COMMANDS + [
    BotCommand(command="warn", description="Выдать предупреждение"),
    BotCommand(command="mute", description="Замутить пользователя"),
    BotCommand(command="ban", description="Забанить пользователя"),
]


async def set_bot_commands(bot: Bot) -> None:
    """
    Default / groups / private: player commands.
    Admins from ADMIN_IDS also get warn/mute/ban in PM and in league chats.
    """
    settings = get_settings()

    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeAllGroupChats())

    league_chats = [
        chat_id
        for chat_id in (settings.main_chat_id, settings.ri_chat_id, settings.vsa_chat_id)
        if chat_id
    ]

    for admin_id in settings.admin_ids:
        try:
            await bot.set_my_commands(
                ADMIN_COMMANDS,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            logger.warning("set_my_commands PM admin=%s failed: %s", admin_id, exc)

        for chat_id in league_chats:
            try:
                await bot.set_my_commands(
                    ADMIN_COMMANDS,
                    scope=BotCommandScopeChatMember(chat_id=chat_id, user_id=admin_id),
                )
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                logger.warning(
                    "set_my_commands chat=%s admin=%s failed: %s",
                    chat_id,
                    admin_id,
                    exc,
                )

    logger.info(
        "Bot commands set: %s user cmds, %s admin ids",
        len(USER_COMMANDS),
        len(settings.admin_ids),
    )
