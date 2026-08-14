from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards import urls
from keyboards.buttons import url_btn
from keyboards.main import back_kb


def ri_menu_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("Календарь Турнира РИ", urls.RI_CALENDAR)],
        [url_btn("Правила Турнира РИ", urls.RI_RULES)],
        [url_btn("Регламент Турнира РИ", urls.RI_REGULATION)],
        [url_btn("Участники Турнира РИ", urls.RI_PARTICIPANTS)],
        [InlineKeyboardButton(text="Премии Турнира РИ", callback_data="menu:ri:awards")],
        [url_btn("Гайд", urls.RI_GUIDE)],
        [InlineKeyboardButton(text="Таблицы", callback_data="menu:ri:tables")],
        [url_btn("Бомбардиры", urls.RI_SCORERS_SHEET)],
        back_to="menu:main",
    )


def ri_awards_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("Премия Зидана", urls.RI_AWARD_ZIDANE)],
        [url_btn("Премия Пушкаша", urls.RI_AWARD_PUSKAS)],
        [url_btn("Премия Яшина", urls.RI_AWARD_YASHIN)],
        [url_btn("Золотой мяч", urls.RI_AWARD_BALLON)],
        [url_btn("Лучший Прогресс", urls.RI_AWARD_PROGRESS)],
        back_to="menu:ri",
    )


def ri_tables_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("Скачать таблицы", urls.RI_TABLES_DOWNLOAD)],
        [InlineKeyboardButton(text="ЛЧ", callback_data="menu:ri:tables:ucl")],
        [InlineKeyboardButton(text="ЛЕ", callback_data="menu:ri:tables:uel")],
        [InlineKeyboardButton(text="ЛК", callback_data="menu:ri:tables:uecl")],
        [InlineKeyboardButton(text="Чемпионаты", callback_data="menu:ri:tables:leagues")],
        [InlineKeyboardButton(text="Кубки", callback_data="menu:ri:tables:cups")],
        [InlineKeyboardButton(text="Суперкубки", callback_data="menu:ri:tables:sc")],
        back_to="menu:ri",
    )


def ri_ucl_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("ЛЧ Группы", urls.UCL_GROUPS)],
        [url_btn("ЛЧ Плей-офф", urls.UCL_PLAYOFF)],
        [url_btn("Таблица", urls.UCL_TABLE)],
        back_to="menu:ri:tables",
    )


def ri_uel_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("ЛЕ Группы", urls.UEL_GROUPS)],
        [url_btn("ЛЕ Плей-офф", urls.UEL_PLAYOFF)],
        [url_btn("Таблица", urls.UEL_TABLE)],
        back_to="menu:ri:tables",
    )


def ri_uecl_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("ЛК Группы", urls.UCL_CONF_GROUPS)],
        [url_btn("ЛК Плей-офф", urls.UCL_CONF_PLAYOFF)],
        [url_btn("Таблица", urls.UCL_CONF_TABLE)],
        back_to="menu:ri:tables",
    )


def ri_leagues_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("АПЛ", urls.APL)],
        [url_btn("ЛаЛига", urls.LALIGA)],
        [url_btn("Серия А", urls.SERIE_A)],
        [url_btn("Бундеслига", urls.BUNDESLIGA)],
        [url_btn("Таблица", urls.LEAGUES_TABLE)],
        back_to="menu:ri:tables",
    )


def ri_cups_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("Кубок АПЛ", urls.CUP_APL)],
        [url_btn("Кубок ЛаЛиги", urls.CUP_LALIGA)],
        [url_btn("Кубок Серии А", urls.CUP_SERIE_A)],
        [url_btn("Кубок Бундеслиги", urls.CUP_BUNDESLIGA)],
        [url_btn("Кубок Англии", urls.CUP_ENGLAND)],
        [url_btn("Кубок Испании", urls.CUP_SPAIN)],
        [url_btn("Кубок Италии", urls.CUP_ITALY)],
        [url_btn("Кубок Германии", urls.CUP_GERMANY)],
        [url_btn("Таблица Кубок Лиг", urls.CUPS_LEAGUES_TABLE)],
        [url_btn("Таблица Кубок Стран", urls.CUPS_COUNTRIES_TABLE)],
        back_to="menu:ri:tables",
    )


def ri_super_cups_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("Суперкубок УЕФА", urls.SC_UEFA)],
        [url_btn("Суперкубок Испании", urls.SC_SPAIN)],
        [url_btn("Суперкубок Англии", urls.SC_ENGLAND)],
        [url_btn("Суперкубок Италии", urls.SC_ITALY)],
        [url_btn("Суперкубок Германии", urls.SC_GERMANY)],
        [url_btn("Таблица", urls.SC_TABLE)],
        back_to="menu:ri:tables",
    )
