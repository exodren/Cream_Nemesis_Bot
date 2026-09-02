from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.main import back_kb


def tova_menu_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [InlineKeyboardButton(text="Регистрация", callback_data="menu:tova:reg")],
        [InlineKeyboardButton(text="Правила", callback_data="menu:tova:rules")],
        [InlineKeyboardButton(text="Как сыграть в TOVA", callback_data="menu:tova:howto")],
        [InlineKeyboardButton(text="Статистика сезона", callback_data="menu:tova:season")],
        [InlineKeyboardButton(text="Архив сезонов", callback_data="menu:tova:archive")],
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


def tova_confirm_kb(match_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"tova:confirm:{match_id}:1",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"tova:confirm:{match_id}:0",
                ),
            ]
        ]
    )


def tova_admin_review_kb(match_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Засчитать",
                    callback_data=f"tova:admin:{match_id}:1",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"tova:admin:{match_id}:0",
                ),
            ]
        ]
    )


def tova_archive_list_kb(seasons: list[int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Сезон #{number}", callback_data=f"menu:tova:archive:{number}")]
        for number in seasons
    ]
    return back_kb(*rows, back_to="menu:tova")


def tova_archive_season_kb(season: int) -> InlineKeyboardMarkup:
    return back_kb(
        [
            InlineKeyboardButton(
                text="Статистика сезона",
                callback_data=f"menu:tova:archive:{season}:stats",
            )
        ],
        [
            InlineKeyboardButton(
                text="Таблица TOVA",
                callback_data=f"menu:tova:archive:{season}:table",
            )
        ],
        [
            InlineKeyboardButton(
                text="Бомбардиры TOVA",
                callback_data=f"menu:tova:archive:{season}:scorers",
            )
        ],
        back_to="menu:tova:archive",
    )
