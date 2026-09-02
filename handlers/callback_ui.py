from __future__ import annotations

from io import BytesIO

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup


def _is_not_modified(exc: TelegramBadRequest) -> bool:
    return "message is not modified" in str(exc).lower()


async def edit_screen(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    *,
    answer: bool = True,
) -> None:
    """Show a text screen by editing the callback message when possible."""
    if answer:
        await callback.answer()
    message = callback.message
    if message is None:
        return

    if message.photo or message.document:
        try:
            await message.delete()
        except TelegramBadRequest:
            pass
        await message.answer(text, reply_markup=reply_markup)
        return

    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if _is_not_modified(exc):
            return
        await message.answer(text, reply_markup=reply_markup)


async def send_photo_pages(
    callback: CallbackQuery,
    pages: list[BytesIO],
    *,
    filename_prefix: str,
    final_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Replace the callback message with one or more photo pages."""
    await callback.answer()
    message = callback.message
    if message is None or not pages:
        return

    try:
        await message.delete()
    except TelegramBadRequest:
        pass

    chat_id = message.chat.id
    bot = callback.bot
    for idx, buf in enumerate(pages):
        file = BufferedInputFile(buf.getvalue(), filename=f"{filename_prefix}_{idx + 1}.png")
        markup = final_markup if idx == len(pages) - 1 else None
        await bot.send_photo(chat_id, file, reply_markup=markup)
