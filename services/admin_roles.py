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

# Minimum level per moderation action: 1-2 mute only, 3 + warns, 4-5 everything.
MIN_LEVEL_MUTE = 1
MIN_LEVEL_WARN = 3
MIN_LEVEL_BAN = 4

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
    3. Settings SUPER_ADMIN_* → 5, ADMIN_IDS / ADMIN_USERNAMES → 1
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

    # 4. Fallback to config settings
    level = 0
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
    """Seed admin_roles on startup.

    Priority:
    1. SUPER_ADMIN_IDS from .env  → level 5 (Владелец) — seeded by tg_id directly, no DB user needed.
    2. SUPER_ADMIN_USERNAMES from .env → level 4 (Главный администратор) after the first ID in SUPER_ADMIN_IDS.
       Actually: first entry → level 5, remaining entries in SUPER_ADMIN_USERNAMES → level 4.    """
    settings = get_settings()

    # --- Seed from .env SUPER_ADMIN_IDS (by Telegram ID) ---
    super_ids = settings.super_admin_ids  # list[int]
    super_usernames = settings.super_admin_usernames  # list[str] (lowercase, no @)

    for idx, tg_id in enumerate(super_ids):
        result = await session.execute(
            select(AdminRole).where(AdminRole.user_id == tg_id)
        )
        existing = result.scalar_one_or_none()
        level = 5  # All IDs in SUPER_ADMIN_IDS get level 5 (immunity)
        uname = super_usernames[idx] if idx < len(super_usernames) else None
        if existing is None:
            session.add(
                AdminRole(
                    user_id=tg_id,
                    username=uname,
                    admin_level=level,
                )
            )
            logger.info("bootstrap: seeded admin_roles user_id=%s level=%s", tg_id, level)
        else:
            # Only upgrade level, never downgrade super admins
            if existing.admin_level < level:
                existing.admin_level = level
                logger.info("bootstrap: upgraded admin_roles user_id=%s to level=%s", tg_id, level)
            if uname and not existing.username:
                existing.username = uname

    # --- Seed remaining SUPER_ADMIN_USERNAMES as level 4 if not already seeded ---
    # (usernames beyond the count of SUPER_ADMIN_IDS)
    for idx in range(len(super_ids), len(super_usernames)):
        uname = super_usernames[idx]
        result_by_name = await session.execute(
            select(AdminRole).where(AdminRole.username.ilike(uname))
        )
        existing = result_by_name.scalar_one_or_none()
        if existing is None:
            # Try to find tg_id from users table
            user_res = await session.execute(
                select(User).where(User.username.ilike(uname))
            )
            user = user_res.scalar_one_or_none()
            if user and user.tg_id:
                session.add(
                    AdminRole(
                        user_id=user.tg_id,
                        username=uname,
                        admin_level=4,
                    )
                )
                logger.info("bootstrap: seeded admin_roles username=%s level=4", uname)

    await session.flush()



async def max_assignable_level(session: AsyncSession, user_id: int, username: str | None) -> int | None:
    """Highest level the initiator may assign: owners 5, level 4 → 3, others None."""
    settings = get_settings()
    level = await get_user_admin_level(session, user_id, username)
    if user_id in settings.super_admin_ids or settings.is_super_admin(user_id, username) or level == 5:
        return 5
    return level - 1 if level == 4 else None


async def list_admins(session: AsyncSession) -> list[AdminRole]:
    result = await session.execute(
        select(AdminRole).where(AdminRole.admin_level > 0).order_by(AdminRole.admin_level.desc())
    )
    return list(result.scalars())


async def assign_admin_level(
    session: AsyncSession, bot: Bot, chat_id: int, target: User, level: int, max_level: int
) -> str:
    """Check rights, save level to DB, sync Telegram rights, return report text."""
    current = await get_user_admin_level(session, target.tg_id, target.username)
    if level > max_level or current > max_level:
        return f"❌ Недостаточно прав: вы можете управлять только уровнями 0–{max_level}."
    await set_user_admin_level(session, user_id=target.tg_id, level=level, username=target.username)
    await session.commit()
    ok, err = await sync_telegram_admin_rights(bot, chat_id=chat_id, user_id=target.tg_id, level=level)
    mention = f"@{target.username}" if target.username else f"ID: {target.tg_id}"
    if level == 0:
        msg = f"ℹ️ Пользователь {mention} разжалован до обычного участника (Уровень 0)."
    else:
        msg = f"✅ Пользователю {mention} назначен ранг: <b>{ROLE_NAMES[level]}</b> (Уровень {level})."
    if ok:
        return msg + "\nПрава администратора в Telegram-чате успешно синхронизированы."
    return msg + f"\n\n⚠️ <i>Предупреждение по Telegram API:</i>\n{err}"
