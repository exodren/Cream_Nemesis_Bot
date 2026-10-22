from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings


class AdminFilter(BaseFilter):
    """
    Allow only bot admins.

    By default:
    - Settings.is_admin or Settings.is_super_admin (ADMIN_IDS, ADMIN_USERNAMES, SUPER_ADMIN_IDS, SUPER_ADMIN_USERNAMES)
    - Or admin_level >= 1 from DB (admin_roles table)
    With strict_ids=True: only numeric ADMIN_IDS / SUPER_ADMIN_IDS (e.g. season management).
    """

    def __init__(self, *, strict_ids: bool = False) -> None:
        self.strict_ids = strict_ids

    async def __call__(self, event: TelegramObject, session: AsyncSession | None = None) -> bool:
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user
        if user is None:
            return False

        settings = get_settings()
        if self.strict_ids:
            return user.id in settings.admin_ids or user.id in settings.super_admin_ids

        # Fast check against config
        if settings.is_admin(user.id, user.username) or settings.is_super_admin(user.id, user.username):
            return True

        # Database role check (level >= 1)
        if session is not None:
            from services.admin_roles import get_user_admin_level

            level = await get_user_admin_level(session, user.id, user.username)
            if level >= 1:
                return True

        return False
