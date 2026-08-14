from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.main import back_kb


def tova_menu_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [InlineKeyboardButton(text="Регистрация", callback_data="menu:tova:reg")],
        [InlineKeyboardButton(text="Правила", callback_data="menu:tova:rules")],
        [InlineKeyboardButton(text="Как сыграть в TOVA", callback_data="menu:tova:howto")],
        [InlineKeyboardButton(text="Статистика сезона", callback_data="menu:tova:season")],
        [InlineKeyboardButton(text="Таблица TOVA", callback_data="menu:tova:table")],
        [InlineKeyboardButton(text="Бомбардиры TOVA", callback_data="menu:tova:scorers")],
        [InlineKeyboardButton(text="Статистика", callback_data="menu:tova:stats")],
        back_to="menu:main",
    )


def tova_reg_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [InlineKeyboardButton(text="Изменить никнейм", callback_data="menu:tova:reg:set")],
        [InlineKeyboardButton(text="Удалить никнейм", callback_data="menu:tova:reg:del")],
        back_to="menu:tova",
    )
