from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from keyboards import urls
from keyboards.buttons import url_btn
from keyboards.main import back_kb


def hall_menu_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("Зал Славы CN", urls.HALL_OF_FAME_CN)],
        [url_btn("Зал Славы РИ", urls.RI_HALL_OF_FAME)],
        [url_btn("Зал Славы VSA", urls.VSA_HALL_OF_FAME)],
        back_to="menu:main",
    )
