from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards.main import back_kb
from services.admin_roles import ROLE_NAMES


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
                text="Администраторы",
                callback_data="admin:roles",
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


def admin_roles_kb(admins: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{a.admin_level} · @{a.username}" if a.username else f"{a.admin_level} · {a.user_id}",
            callback_data=f"admin:roles:pick:{a.user_id}",
        )]
        for a in admins
    ]
    rows.append([InlineKeyboardButton(text="➕ Назначить администратора", callback_data="admin:roles:add")])
    return back_kb(*rows, back_to="admin:panel")


def admin_level_kb(user_id: int, max_level: int) -> InlineKeyboardMarkup:
    return back_kb(
        *[
            [InlineKeyboardButton(text=f"{lvl} — {ROLE_NAMES[lvl]}", callback_data=f"admin:roles:set:{user_id}:{lvl}")]
            for lvl in range(max_level, -1, -1)
        ],
        back_to="admin:roles",
    )
