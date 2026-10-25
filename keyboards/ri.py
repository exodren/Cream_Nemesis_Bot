from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards import urls
from keyboards.buttons import url_btn
from keyboards.main import back_kb


def ri_menu_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [InlineKeyboardButton(text="Таблицы", callback_data="menu:ri:tables")],
        [url_btn("Бомбардиры", urls.RI_SCORERS_SHEET)],
        back_to="menu:main",
    )


def ri_tables_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("Скачать таблицы", urls.RI_TABLES_DOWNLOAD)],
        [url_btn("ЛЧ / ЛЕ / ЛК", urls.EUROCUPS_TABLE)],
        [url_btn("Чемпионаты", urls.LEAGUES_TABLE)],
        [url_btn("Кубок Лиг", urls.CUPS_LEAGUES_TABLE)],
        [url_btn("Кубок Стран", urls.CUPS_COUNTRIES_TABLE)],
        [url_btn("Суперкубки", urls.SC_TABLE)],
        back_to="menu:ri",
    )
