from __future__ import annotations

from aiogram.types import InlineKeyboardButton

TOPIC_MISSING_CB = "menu:topic_missing"


def url_btn(text: str, url: str | None) -> InlineKeyboardButton:
    """URL-кнопка; если тема не задана в .env — callback вместо битой ссылки."""
    if url:
        return InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardButton(text=text, callback_data=TOPIC_MISSING_CB)
