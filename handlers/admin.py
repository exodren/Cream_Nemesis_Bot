from __future__ import annotations

import logging
import re

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from services import moderation as mod
from services import users as users_service

router = Router(name="admin")
logger = logging.getLogger(__name__)

MENTION_RE = re.compile(r"@(\w+)")


def _is_admin(user_id: int, username: str | None = None) -> bool:
    return get_settings().is_admin(user_id, username)


def _target_chat_id(message: Message) -> int:
    """
    Moderate in the chat where the command was sent.
    MAIN_CHAT_ID from .env is only a fallback for private-chat commands.
    """
    if message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return message.chat.id
    settings = get_settings()
    return settings.main_chat_id or message.chat.id


async def _resolve_from_message(
    message: Message,
    session: AsyncSession,
    parts: list[str],
) -> tuple[object | None, str | None]:
    chat_id = _target_chat_id(message)

    # reply
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        if target.is_bot:
            return None, "Нельзя применять модерацию к боту."
        user = await users_service.get_or_create_user(
            session,
            tg_id=target.id,
            username=target.username,
        )
        return user, None

    # @username in args
    if len(parts) >= 2:
        m = MENTION_RE.search(parts[1])
        username = m.group(1) if m else parts[1].lstrip("@")
        return await mod.resolve_target_user(
            session,
            bot=message.bot,
            chat_id=chat_id,
            username=username,
        )

    return None, "Укажите @username или ответьте на сообщение пользователя."


@router.message(Command("warn"))
async def cmd_warn(message: Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, message.from_user.username):
        return

    parts = (message.text or "").split()
    user, err = await _resolve_from_message(message, session, parts)
    if err or user is None:
        await message.answer(err or "Пользователь не найден.")
        return

    reason = " ".join(parts[2:]) if len(parts) > 2 else None
    count = await mod.add_warning(
        session,
        user=user,
        admin_tg_id=message.from_user.id,
        reason=reason,
    )
    mention = f"@{user.username}" if user.username else str(user.tg_id)
    chat_id = _target_chat_id(message)
    await message.answer(
        f"Предупреждение выдано {mention}.\nАктивных предупреждений: {count}/3"
    )

    if count >= 3:
        user.is_banned = True
        ok, api_err = await mod.safe_ban(message.bot, chat_id, user.tg_id)
        logger.info("warn->ban chat=%s user=%s ok=%s err=%s", chat_id, user.tg_id, ok, api_err)
        if ok:
            await message.answer(
                f"{mention} получил 3 предупреждения и заблокирован."
            )
        else:
            await message.answer(
                f"3 предупреждения зафиксированы, но кик/бан не выполнен.\n{api_err}"
            )


@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, message.from_user.username):
        return

    parts = (message.text or "").split()
    user, err = await _resolve_from_message(message, session, parts)
    if err or user is None:
        await message.answer(err or "Пользователь не найден.")
        return

    count = await mod.remove_one_warning(session, user)
    mention = f"@{user.username}" if user.username else str(user.tg_id)
    await message.answer(
        f"Снято одно предупреждение с {mention}.\nАктивных: {count}/3"
    )


@router.message(Command("mute"))
async def cmd_mute(message: Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, message.from_user.username):
        return

    parts = (message.text or "").split()
    minutes = 60
    if message.reply_to_message:
        if len(parts) >= 2 and parts[1].isdigit():
            minutes = int(parts[1])
        user, err = await _resolve_from_message(message, session, parts)
    else:
        if len(parts) < 3 or not parts[2].isdigit():
            await message.answer("Формат: /mute @user 60\nИли reply на сообщение: /mute 60")
            return
        minutes = int(parts[2])
        user, err = await _resolve_from_message(message, session, parts)

    if err or user is None:
        await message.answer(err or "Пользователь не найден.")
        return

    chat_id = _target_chat_id(message)
    ok, api_err = await mod.safe_mute(message.bot, chat_id, user.tg_id, minutes)
    logger.info("mute chat=%s user=%s min=%s ok=%s err=%s", chat_id, user.tg_id, minutes, ok, api_err)
    mention = f"@{user.username}" if user.username else str(user.tg_id)
    if ok:
        await message.answer(f"{mention} в муте на {minutes} мин.")
    else:
        await message.answer(api_err or "Не удалось выдать мут.")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, message.from_user.username):
        return

    parts = (message.text or "").split()
    user, err = await _resolve_from_message(message, session, parts)
    if err or user is None:
        await message.answer(err or "Пользователь не найден.")
        return

    chat_id = _target_chat_id(message)
    ok, api_err = await mod.safe_unmute(message.bot, chat_id, user.tg_id)
    logger.info("unmute chat=%s user=%s ok=%s err=%s", chat_id, user.tg_id, ok, api_err)
    mention = f"@{user.username}" if user.username else str(user.tg_id)
    if ok:
        await message.answer(f"Мут снят с {mention}.")
    else:
        await message.answer(api_err or "Не удалось снять мут.")


@router.message(Command("ban"))
async def cmd_ban(message: Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, message.from_user.username):
        return

    parts = (message.text or "").split()
    user, err = await _resolve_from_message(message, session, parts)
    if err or user is None:
        await message.answer(err or "Пользователь не найден.")
        return

    chat_id = _target_chat_id(message)
    user.is_banned = True
    ok, api_err = await mod.safe_ban(message.bot, chat_id, user.tg_id)
    logger.info("ban chat=%s user=%s ok=%s err=%s", chat_id, user.tg_id, ok, api_err)
    mention = f"@{user.username}" if user.username else str(user.tg_id)
    if ok:
        await message.answer(f"{mention} забанен.")
    else:
        await message.answer(
            f"Пользователь помечен как banned в БД, но кик не выполнен.\n{api_err}"
        )


@router.message(Command("unban"))
async def cmd_unban(message: Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, message.from_user.username):
        return

    parts = (message.text or "").split()
    user, err = await _resolve_from_message(message, session, parts)
    if err or user is None:
        await message.answer(err or "Пользователь не найден.")
        return

    chat_id = _target_chat_id(message)
    user.is_banned = False
    ok, api_err = await mod.safe_unban(message.bot, chat_id, user.tg_id)
    logger.info("unban chat=%s user=%s ok=%s err=%s", chat_id, user.tg_id, ok, api_err)
    mention = f"@{user.username}" if user.username else str(user.tg_id)
    if ok:
        await message.answer(f"{mention} разбанен.")
    else:
        await message.answer(
            f"Флаг бана снят в БД, но unban в чате не выполнен.\n{api_err}"
        )
