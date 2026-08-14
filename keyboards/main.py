from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from texts import BACK, MAIN_MENU


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="РЕГЛАМЕНТ / АКТИВ", callback_data="menu:regulation")
    )
    builder.row(InlineKeyboardButton(text="ПРАВИЛА CN", callback_data="menu:rules"))
    builder.row(InlineKeyboardButton(text="ЛПЛ", callback_data="menu:lpl"))
    builder.row(
        InlineKeyboardButton(text="Режим Тренера", callback_data="menu:coach")
    )
    builder.row(InlineKeyboardButton(text="Турниры РИ", callback_data="menu:ri"))
    builder.row(
        InlineKeyboardButton(text="Турнир по ВСА", callback_data="menu:vsa")
    )
    builder.row(
        InlineKeyboardButton(text="Зал Славы CN", callback_data="menu:hall")
    )
    builder.row(InlineKeyboardButton(text="Админы", callback_data="menu:admins"))
    builder.row(InlineKeyboardButton(text="TOVA", callback_data="menu:tova"))
    return builder.as_markup()


def back_kb(*rows: list[InlineKeyboardButton], back_to: str = "menu:main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.row(*row)
    nav = [InlineKeyboardButton(text=BACK, callback_data=back_to)]
    if back_to != "menu:main":
        nav.append(InlineKeyboardButton(text=MAIN_MENU, callback_data="menu:main"))
    builder.row(*nav)
    return builder.as_markup()


def back_only_kb(back_to: str = "menu:main") -> InlineKeyboardMarkup:
    return back_kb(back_to=back_to)
