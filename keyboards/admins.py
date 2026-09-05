from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import get_settings
from keyboards.main import back_kb


LEAGUE_TITLES = {
    "cn": "Cream Nemesis",
    "lpl": "ЛПЛ",
    "ri": "РИ",
    "vsa": "ВСА",
    "tova": "TOVA",
}


def _mention_line(usernames: list[str]) -> str:
    if not usernames:
        return "пока не указаны"
    return ", ".join(f"@{name}" for name in usernames)


def admins_overview_text() -> str:
    settings = get_settings()
    cn_mentions = _mention_line(settings.league_admins.get("cn", []))
    lines = [
        f"<b>Основатели Cream Nemesis:</b> {cn_mentions}",
        "",
        "<b>Админы</b>",
    ]
    for key, title in LEAGUE_TITLES.items():
        if key == "cn":
            continue
        lines.append(f"<b>{title}:</b> {_mention_line(settings.league_admins.get(key, []))}")
    lines.append("\nВыберите лигу, чтобы открыть профили:")
    return "\n".join(lines)


def admins_league_text(league: str) -> str:
    settings = get_settings()
    title = LEAGUE_TITLES.get(league, league)
    header = f"Основатели {title}" if league == "cn" else f"Админы {title}"
    names = settings.league_admins.get(league, [])
    if not names:
        return f"<b>{header}</b>\n\nПока не указаны в .env"
    listed = "\n".join(f"• @{name}" for name in names)
    return f"<b>{header}</b>\n\n{listed}"


def admins_menu_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [InlineKeyboardButton(text="Cream Nemesis", callback_data="menu:admins:cn")],
        [InlineKeyboardButton(text="ЛПЛ", callback_data="menu:admins:lpl")],
        [InlineKeyboardButton(text="РИ", callback_data="menu:admins:ri")],
        [InlineKeyboardButton(text="ВСА", callback_data="menu:admins:vsa")],
        [InlineKeyboardButton(text="TOVA", callback_data="menu:admins:tova")],
        back_to="menu:main",
    )


def admins_league_kb(league: str) -> InlineKeyboardMarkup:
    settings = get_settings()
    names = settings.league_admins.get(league, [])
    rows = [
        [InlineKeyboardButton(text=f"@{name}", url=f"https://t.me/{name}")]
        for name in names
    ]
    return back_kb(*rows, back_to="menu:admins")
