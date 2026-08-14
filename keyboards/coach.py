from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from keyboards import urls
from keyboards.buttons import url_btn
from keyboards.main import back_kb


def coach_kb() -> InlineKeyboardMarkup:
    return back_kb(
        [url_btn("Открыть Режим Тренера", urls.COACH_MODE)],
        back_to="menu:main",
    )
