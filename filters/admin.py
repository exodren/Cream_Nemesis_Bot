from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import get_settings


class AdminFilter(BaseFilter):
    """
    Allow only bot admins.

    By default: ADMIN_IDS + ADMIN_USERNAMES (Settings.is_admin).
    With strict_ids=True: only numeric ADMIN_IDS (e.g. season management).
    """

    def __init__(self, *, strict_ids: bool = False) -> None:
        self.strict_ids = strict_ids

    async def __call__(self, event: TelegramObject) -> bool:
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        if user is None:
            return False

        settings = get_settings()
        if self.strict_ids:
            return user.id in settings.admin_ids
        return settings.is_admin(user.id, user.username)
