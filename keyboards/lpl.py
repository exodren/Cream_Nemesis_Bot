from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards import urls
from keyboards.buttons import url_btn
from keyboards.main import back_kb


def lpl_menu_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [InlineKeyboardButton(text="Правила ЛПЛ", callback_data="menu:lpl:rules")],
        [url_btn("Статистика ЛПЛ", urls.LPL_STATS)],
        [url_btn("Бомбардиры ЛПЛ", urls.LPL_SCORERS)],
        [url_btn("Состав ЛПЛ", urls.LPL_ROSTER)],
        back_to="menu:main",
    )


def lpl_rules_kb() -> InlineKeyboardMarkup:
    return back_kb(back_to="menu:lpl")
