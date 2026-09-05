from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.main import back_kb


def admin_panel_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [
            InlineKeyboardButton(
                text="Управление сезонами TOVA",
                callback_data="admin:seasons",
            )
        ],
        [
            InlineKeyboardButton(
                text="Активные варны",
                callback_data="admin:warns",
            )
        ],
        [
            InlineKeyboardButton(
                text="Управление составом ЛПЛ",
                callback_data="admin:lpl_roster",
            )
        ],
        [
            InlineKeyboardButton(
                text="Отправить тег ЛПЛ сейчас",
                callback_data="admin:lpl_tag_now",
            )
        ],
        [
            InlineKeyboardButton(
                text="Справка модерации",
                callback_data="admin:help",
            )
        ],
        back_to="menu:main",
    )


def admin_lpl_roster_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [
            InlineKeyboardButton(
                text="Загрузить новый состав",
                callback_data="admin:lpl_roster:upload",
            )
        ],
        [
            InlineKeyboardButton(
                text="Показать текущий состав",
                callback_data="admin:lpl_roster:show",
            )
        ],
        [
            InlineKeyboardButton(
                text="Очистить состав",
                callback_data="admin:lpl_roster:clear",
            )
        ],
        back_to="admin:panel",
    )


def admin_seasons_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [
            InlineKeyboardButton(
                text="Завершить текущий сезон",
                callback_data="season:end",
            )
        ],
        [
            InlineKeyboardButton(
                text="Начать новый сезон",
                callback_data="season:start",
            )
        ],
        back_to="admin:panel",
    )
