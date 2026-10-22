from __future__ import annotations

import json
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import AdminRole, User

logger = logging.getLogger(__name__)

# Default role mapping per technical specification:
# Уровень 5: Владелец (@Fara1807, @hushjournal)
# Уровень 4: Главный администратор (@nTarasov00)
# Уровень 3: Старший модератор (@FinrirX)
# Уровень 2: Модератор (@B4knur)
# Уровень 1: Младший модератор (@Azheke_GB)
# Уровень 0: Обычный участник лиги
DEFAULT_ADMIN_LEVELS: dict[str, int] = {
    "fara1807": 5,
    "hushjournal": 5,
    "ntarasov00": 4,
    "finrirx": 3,
    "b4knur": 2,
    "azheke_gb": 1,
}

ROLE_NAMES: dict[int, str] = {
    5: "Владелец",
    4: "Главный администратор",
    3: "Старший модератор",
    2: "Модератор",
    1: "Младший модератор",
    0: "Обычный участник",
}

DEMOTE_PROMOTION_KWARGS = {
    "is_anonymous": False,
    "can_manage_chat": False,
    "can_delete_messages": False,
    "can_manage_video_chats": False,
    "can_restrict_members": False,
    "can_promote_members": False,
    "can_change_info": False,
    "can_invite_users": False,
    "can_post_stories": False,
    "can_edit_stories": False,
    "can_delete_stories": False,
    "can_post_messages": False,
    "can_edit_messages": False,
    "can_pin_messages": False,
    "can_manage_topics": False,
}

LEVEL_PERMISSIONS: dict[int, dict[str, bool]] = {
    5: {
        # Уровень 5: Владелец — полные права + назначение админов
        "is_anonymous": False,
        "can_manage_chat": True,
        "can_delete_messages": True,
        "can_manage_video_chats": True,
        "can_restrict_members": True,
        "can_promote_members": True,
        "can_change_info": True,
        "can_invite_users": True,
        "can_pin_messages": True,
        "can_manage_topics": True,
    },
    4: {
        # Уровень 4: Главный администратор — управление чатом, мут, бан, закрепление
        "is_anonymous": False,
        "can_manage_chat": True,
        "can_delete_messages": True,
        "can_manage_video_chats": True,
        "can_restrict_members": True,
        "can_promote_members": False,
        "can_change_info": True,
        "can_invite_users": True,
        "can_pin_messages": True,
        "can_manage_topics": True,
    },
    3: {
        # Уровень 3: Старший модератор — мут, бан, удаление, закреп, темы
        "is_anonymous": False,
        "can_manage_chat": False,
        "can_delete_messages": True,
        "can_manage_video_chats": True,
        "can_restrict_members": True,
        "can_promote_members": False,
        "can_change_info": False,
        "can_invite_users": True,
        "can_pin_messages": True,
        "can_manage_topics": True,
    },
    2: {
        # Уровень 2: Модератор — удаление сообщений, мут/ограничение, инвайт
        "is_anonymous": False,
        "can_manage_chat": False,
        "can_delete_messages": True,
        "can_manage_video_chats": False,
        "can_restrict_members": True,
        "can_promote_members": False,
        "can_change_info": False,
        "can_invite_users": True,
        "can_pin_messages": False,
        "can_manage_topics": False,
    },
    1: {
        # Уровень 1: Младший модератор — удаление сообщений, инвайт
        "is_anonymous": False,
        "can_manage_chat": False,
        "can_delete_messages": True,
        "can_manage_video_chats": False,
        "can_restrict_members": False,
        "can_promote_members": False,
        "can_change_info": False,
        "can_invite_users": True,
        "can_pin_messages": False,
        "can_manage_topics": False,
    },
}


def get_default_level_for_username(username: str | None) -> int:
    if not username:
        return 0
    clean = username.lstrip("@").lower()
    return DEFAULT_ADMIN_LEVELS.get(clean, 0)


async def get_user_admin_level(
    session: AsyncSession,
    user_id: int,
    username: str | None = None,
) -> int:
    """
    Get admin level (0-5) for a user by user_id or username.
    Checks:
    1. admin_roles table by user_id
    2. admin_roles table by username
    3. DEFAULT_ADMIN_LEVELS matrix
    4. Settings SUPER_ADMIN_IDS / ADMIN_IDS
    """
    settings = get_settings()

    # 1. Check if user is in SUPER_ADMIN_IDS in .env (Level 5)
    if settings.super_admin_ids and user_id in settings.super_admin_ids:
        return 5

    # 2. Check admin_roles by user_id
    result = await session.execute(
        select(AdminRole).where(AdminRole.user_id == user_id)
    )
    role_rec = result.scalar_one_or_none()
    if role_rec is not None:
        if username and not role_rec.username:
            role_rec.username = username.lstrip("@")
            await session.flush()
        return role_rec.admin_level

    # 3. Check admin_roles by username
    if username:
        clean = username.lstrip("@").lower()
        result_by_name = await session.execute(
            select(AdminRole).where(AdminRole.username.ilike(clean))
        )
        role_by_name = result_by_name.scalar_one_or_none()
        if role_by_name is not None:
            return role_by_name.admin_level

    # 4. Fallback to default matrix by username
    level = get_default_level_for_username(username)
    if level > 0:
        new_rec = AdminRole(
            user_id=user_id,
            username=username.lstrip("@") if username else None,
            admin_level=level,
        )
        session.add(new_rec)
        await session.flush()
        return level

    # 5. Fallback to config settings
    if settings.is_super_admin(user_id, username):
        level = 5
    elif settings.is_admin(user_id, username):
        level = 1

    if level > 0:
        new_rec = AdminRole(
            user_id=user_id,
            username=username.lstrip("@") if username else None,
            admin_level=level,
        )
        session.add(new_rec)
        await session.flush()
        return level

    return 0


async def set_user_admin_level(
    session: AsyncSession,
    user_id: int,
    level: int,
    username: str | None = None,
) -> AdminRole:
    level = max(0, min(5, level))
    result = await session.execute(
        select(AdminRole).where(AdminRole.user_id == user_id)
    )
    role_rec = result.scalar_one_or_none()
    if role_rec is not None:
        role_rec.admin_level = level
        if username:
            role_rec.username = username.lstrip("@")
    else:
        role_rec = AdminRole(
            user_id=user_id,
            username=username.lstrip("@") if username else None,
            admin_level=level,
        )
        session.add(role_rec)
    await session.flush()
    return role_rec


async def sync_telegram_admin_rights(
    bot: Bot,
    chat_id: int,
    user_id: int,
    level: int,
    custom_title: str | None = None,
) -> tuple[bool, str | None]:
    """
    Promote or demote user in Telegram chat according to admin_level.
    """
    if level <= 0:
        try:
            await bot.promote_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                **DEMOTE_PROMOTION_KWARGS,
            )
            return True, None
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            msg = getattr(exc, "message", None) or str(exc)
            return False, f"Ошибка разжалования в Telegram: {msg}"
        except Exception as exc:
            return False, f"Ошибка разжалования в Telegram: {exc}"

    perms = LEVEL_PERMISSIONS.get(level, LEVEL_PERMISSIONS[1])
    try:
        await bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            **perms,
        )
        title = custom_title or ROLE_NAMES.get(level)
        if title:
            try:
                await bot.set_chat_administrator_custom_title(
                    chat_id=chat_id,
                    user_id=user_id,
                    custom_title=title,
                )
            except Exception:
                pass
        return True, None
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        msg = getattr(exc, "message", None) or str(exc)
        return False, (
            f"Не удалось выдать права администратора в Telegram.\n"
            f"Telegram: {msg}\n"
            "Убедитесь, что у бота включено право «Назначение администраторов» "
            "и он находится выше назначаемого пользователя в списке администраторов группы."
        )
    except Exception as exc:
        return False, f"Ошибка Telegram API: {exc}"


async def save_admin_permissions(
    session: AsyncSession,
    user_id: int,
    permissions: dict,
    username: str | None = None,
) -> None:
    perms_json = json.dumps(permissions)
    result = await session.execute(
        select(AdminRole).where(AdminRole.user_id == user_id)
    )
    role_rec = result.scalar_one_or_none()
    if role_rec is not None:
        role_rec.saved_permissions = perms_json
        if username and not role_rec.username:
            role_rec.username = username.lstrip("@")
    else:
        level = await get_user_admin_level(session, user_id, username)
        role_rec = AdminRole(
            user_id=user_id,
            username=username.lstrip("@") if username else None,
            admin_level=level,
            saved_permissions=perms_json,
        )
        session.add(role_rec)
    await session.flush()


async def get_saved_admin_permissions(
    session: AsyncSession,
    user_id: int,
) -> dict | None:
    result = await session.execute(
        select(AdminRole.saved_permissions).where(AdminRole.user_id == user_id)
    )
    perms_raw = result.scalar_one_or_none()
    if not perms_raw:
        return None
    try:
        return json.loads(perms_raw)
    except Exception:
        return None


async def clear_saved_admin_permissions(
    session: AsyncSession,
    user_id: int,
) -> None:
    result = await session.execute(
        select(AdminRole).where(AdminRole.user_id == user_id)
    )
    role_rec = result.scalar_one_or_none()
    if role_rec is not None:
        role_rec.saved_permissions = None
        await session.flush()


async def bootstrap_admin_roles(session: AsyncSession) -> None:
    """Populate admin_roles from known users matching default usernames."""
    for uname, default_level in DEFAULT_ADMIN_LEVELS.items():
        user_res = await session.execute(
            select(User).where(User.username.ilike(uname))
        )
        user = user_res.scalar_one_or_none()
        if user and user.tg_id:
            role_res = await session.execute(
                select(AdminRole).where(AdminRole.user_id == user.tg_id)
            )
            if role_res.scalar_one_or_none() is None:
                session.add(
                    AdminRole(
                        user_id=user.tg_id,
                        username=user.username or uname,
                        admin_level=default_level,
                    )
                )
    await session.flush()
