from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatType
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def bot_deep_link(bot: Bot, payload: str = "") -> str:
    me = await bot.get_me()
    username = me.username or "CreamNemesis_bot"
    if payload:
        return f"https://t.me/{username}?start={payload}"
    return f"https://t.me/{username}"


def private_redirect_kb(url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Открыть бота в ЛС", url=url))
    return builder.as_markup()


async def ensure_private(
    message: Message,
    *,
    hint: str = "Продолжите действие в личных сообщениях с ботом.",
) -> bool:
    if message.chat.type == ChatType.PRIVATE:
        return True
    url = await bot_deep_link(message.bot, "tova")
    await message.reply(
        f"{hint}\n\nНапишите боту в ЛС и продолжите там.",
        reply_markup=private_redirect_kb(url),
    )
    return False


async def ensure_private_callback(callback_message_chat_type: str) -> bool:
    return callback_message_chat_type == ChatType.PRIVATE
