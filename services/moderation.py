import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (
    ChatMemberAdministrator,
    ChatMemberOwner,
    ChatPermissions,
)
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from db.base import async_session
from db.models import MutedAdmin, User, Warning
from services import admin_roles as admin_roles_service
from services import users as users_service

logger = logging.getLogger(__name__)

RIGHTS_ERROR = (
    "Недостаточно прав. Сделайте бота админом с правом "
    "«Блокировать пользователей» / ограничивать участников."
)

MUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

UNMUTE_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
)

WARN_TTL_DAYS = 30


def _api_error(exc: Exception) -> str:
    # Plain text only — no <tags>: global HTML parse_mode would treat them as markup.
    text = getattr(exc, "message", None) or str(exc)
    lowered = text.lower()
    if "not enough rights" in lowered or "chat_admin_required" in lowered:
        return f"{RIGHTS_ERROR}\nTelegram: {text}"
    if "user is an administrator" in lowered or "can't remove chat owner" in lowered:
        return f"Нельзя банить/мутить другого админа или владельца чата.\nTelegram: {text}"
    if "user_not_participant" in lowered or "user not found" in lowered:
        return f"Пользователь не в этом чате или неверный ID.\nTelegram: {text}"
    return f"Ошибка Telegram: {text}"


async def resolve_target_user(
    session: AsyncSession,
    *,
    bot: Bot,
    chat_id: int,
    username: str | None = None,
    user_id: int | None = None,
) -> tuple[User | None, str | None]:
    if user_id is not None:
        user = await users_service.get_or_create_user(session, tg_id=user_id)
        return user, None

    if username:
        clean = username.lstrip("@")
        result = await session.execute(
            select(User).where(User.username.ilike(clean))
        )
        user = result.scalar_one_or_none()
        if user:
            return user, None

        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=f"@{clean}")
            tg_id = member.user.id
            first_name = member.user.first_name
            user = await users_service.get_or_create_user(
                session,
                tg_id=tg_id,
                username=member.user.username or clean,
            )
            if first_name and user.username is None:
                user.username = member.user.username or clean
            return user, None
        except TelegramBadRequest:
            return None, f"Не удалось найти пользователя @{clean} в этом чате."

        return None, (
            f"Пользователь @{clean} не найден в базе бота.\n"
            "Надёжный способ: reply на его сообщение + /ban|/mute.\n"
            "Либо пусть он один раз напишет /start боту (тогда сработает @username)."
        )

    return None, "Укажите @username или ответьте на сообщение пользователя."


async def count_active_warns(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Warning)
        .where(Warning.user_id == user_id, Warning.is_active.is_(True))
    )
    return int(result.scalar_one() or 0)


async def add_warning(
    session: AsyncSession,
    *,
    user: User,
    admin_tg_id: int,
    reason: str | None = None,
    league_nickname: str | None = None,
    username: str | None = None,
) -> int:
    nick = (league_nickname or user.nickname or "").strip() or None
    uname = (username or user.username or "").strip().lstrip("@") or None
    session.add(
        Warning(
            user_id=user.id,
            admin_id=admin_tg_id,
            username=uname,
            league_nickname=nick,
            reason=reason,
            is_active=True,
        )
    )
    await session.flush()
    return await count_active_warns(session, user.id)


async def remove_one_warning(session: AsyncSession, user: User) -> int:
    result = await session.execute(
        select(Warning)
        .where(Warning.user_id == user.id, Warning.is_active.is_(True))
        .order_by(Warning.created_at.desc())
        .limit(1)
    )
    warn = result.scalar_one_or_none()
    if warn is None:
        return await count_active_warns(session, user.id)
    warn.is_active = False
    await session.flush()
    return await count_active_warns(session, user.id)


async def expire_old_warnings(
    session: AsyncSession,
    *,
    days: int = WARN_TTL_DAYS,
) -> int:
    """Deactivate warnings older than `days`. Returns number of rows updated."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        update(Warning)
        .where(Warning.is_active.is_(True), Warning.created_at < cutoff)
        .values(is_active=False)
    )
    await session.flush()
    return int(result.rowcount or 0)


async def list_active_warn_summary(session: AsyncSession) -> list[tuple[str, str, int]]:
    """
    Active warns grouped by user.
    Returns list of (username_display, league_nickname, count).
    """
    result = await session.execute(
        select(Warning)
        .options(selectinload(Warning.user))
        .where(Warning.is_active.is_(True))
        .order_by(Warning.created_at.desc())
    )
    warns = list(result.scalars().all())

    # user_id -> (uname, nick, count)
    buckets: dict[int, tuple[str, str, int]] = {}
    for w in warns:
        user = w.user
        uname = (
            w.username
            or (user.username if user else None)
            or str(user.tg_id if user else w.user_id)
        )
        nick = w.league_nickname or (user.nickname if user else None) or "—"
        if not uname.startswith("@") and not uname.isdigit():
            uname = f"@{uname}"
        elif uname.isdigit():
            uname = f"id:{uname}"
        prev = buckets.get(w.user_id)
        if prev is None:
            buckets[w.user_id] = (uname, nick, 1)
        else:
            buckets[w.user_id] = (prev[0], prev[1] if prev[1] != "—" else nick, prev[2] + 1)

    rows = list(buckets.values())
    rows.sort(key=lambda r: (-r[2], r[0].lower()))
    return rows


def format_active_warns_text(rows: list[tuple[str, str, int]]) -> str:
    if not rows:
        return "<b>Активные варны</b>\n\nСейчас ни у кого нет активных предупреждений."
    lines = ["<b>Активные варны</b>", ""]
    for uname, nick, count in rows:
        lines.append(f"{uname} - {nick} ({count}/3)")
    lines.append("")
    lines.append("<i>Варн сгорает через 30 дней.</i>")
    return "\n".join(lines)


async def safe_ban(bot: Bot, chat_id: int, user_id: int) -> tuple[bool, str | None]:
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        return True, None
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        return False, _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"Ошибка бана: {exc}"


async def safe_unban(bot: Bot, chat_id: int, user_id: int) -> tuple[bool, str | None]:
    try:
        await bot.unban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            only_if_banned=True,
        )
        return True, None
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        return False, _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"Ошибка разбана: {exc}"


async def safe_mute(
    bot: Bot,
    chat_id: int,
    user_id: int,
    minutes: int,
) -> tuple[bool, str | None]:
    until = datetime.now(timezone.utc) + timedelta(minutes=max(1, minutes))
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=MUTE_PERMISSIONS,
            until_date=until,
            use_independent_chat_permissions=True,
        )
        return True, None
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        return False, _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"Ошибка мута: {exc}"


async def safe_unmute(bot: Bot, chat_id: int, user_id: int) -> tuple[bool, str | None]:
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=UNMUTE_PERMISSIONS,
            use_independent_chat_permissions=True,
        )
        return True, None
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        return False, _api_error(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"Ошибка снятия мута: {exc}"


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


def extract_admin_permissions(member: ChatMemberAdministrator) -> dict[str, bool]:
    return {
        "is_anonymous": bool(getattr(member, "is_anonymous", False)),
        "can_manage_chat": bool(getattr(member, "can_manage_chat", False)),
        "can_delete_messages": bool(getattr(member, "can_delete_messages", False)),
        "can_manage_video_chats": bool(getattr(member, "can_manage_video_chats", False)),
        "can_restrict_members": bool(getattr(member, "can_restrict_members", False)),
        "can_promote_members": bool(getattr(member, "can_promote_members", False)),
        "can_change_info": bool(getattr(member, "can_change_info", False)),
        "can_invite_users": bool(getattr(member, "can_invite_users", False)),
        "can_post_stories": bool(getattr(member, "can_post_stories", False)),
        "can_edit_stories": bool(getattr(member, "can_edit_stories", False)),
        "can_delete_stories": bool(getattr(member, "can_delete_stories", False)),
        "can_post_messages": bool(getattr(member, "can_post_messages", False)),
        "can_edit_messages": bool(getattr(member, "can_edit_messages", False)),
        "can_pin_messages": bool(getattr(member, "can_pin_messages", False)),
        "can_manage_topics": bool(getattr(member, "can_manage_topics", False)),
    }


async def check_moderation_rights(
    session: AsyncSession,
    bot: Bot,
    chat_id: int,
    *,
    initiator_id: int,
    initiator_username: str | None,
    target_id: int,
    target_username: str | None,
    min_level: int = 1,
) -> tuple[bool, str | None, ChatMemberAdministrator | None, int, int]:
    """
    Checks 5-level hierarchy and immunity according to role model.
    min_level: lowest initiator level allowed to run this action (see admin_roles.MIN_LEVEL_*).
    Returns: (can_punish, error_message, target_admin_obj_if_admin, initiator_level, target_level)
    """
    # 1. Fetch initiator and target levels from DB / roles
    initiator_level = await admin_roles_service.get_user_admin_level(
        session, initiator_id, initiator_username
    )
    if initiator_level < min_level:
        return False, f"Недостаточно прав: команда доступна с уровня {min_level}.", None, initiator_level, 0
    target_level = await admin_roles_service.get_user_admin_level(
        session, target_id, target_username
    )

    target_chat_member = None
    try:
        target_chat_member = await asyncio.wait_for(
            bot.get_chat_member(chat_id=chat_id, user_id=target_id),
            timeout=8.0,
        )
    except Exception as e:
        logger.debug("Could not get chat member for %s in %s: %s", target_id, chat_id, e)

    # Chat owner has top immunity (Level 5)
    if isinstance(target_chat_member, ChatMemberOwner) or (
        target_chat_member and getattr(target_chat_member, "status", "") == "creator"
    ):
        target_level = max(target_level, 5)

    # If target is Telegram chat administrator but has level 0 in DB, assign at least level 1
    if isinstance(target_chat_member, ChatMemberAdministrator) and target_level == 0:
        target_level = 1

    # 2. Immunity of Top tier (Levels 5 and 4)
    # Обладают абсолютной защитой от любых команд модерации со стороны других администраторов.
    if target_level in (4, 5):
        return (
            False,
            "Владельцу нельзя применять ограничения",
            None,
            initiator_level,
            target_level,
        )

    # 3. Strict hierarchy principle: X can punish Y only if X > Y
    if initiator_level <= target_level:
        return (
            False,
            "Недостаточно прав",
            None,
            initiator_level,
            target_level,
        )

    # Target is regular user (level 0) or junior admin (levels 1-3)
    admin_obj = (
        target_chat_member
        if isinstance(target_chat_member, ChatMemberAdministrator)
        else None
    )
    return True, None, admin_obj, initiator_level, target_level


async def is_admin_muted(session: AsyncSession, chat_id: int, user_id: int) -> bool:
    saved = await admin_roles_service.get_saved_admin_permissions(session, user_id)
    if saved is not None:
        return True

    result = await session.execute(
        select(MutedAdmin.id)
        .where(
            MutedAdmin.chat_id == chat_id,
            MutedAdmin.user_id == user_id,
            MutedAdmin.is_active.is_(True),
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def mute_junior_admin(
    bot: Bot,
    session: AsyncSession,
    *,
    chat_id: int,
    target_id: int,
    target_username: str | None,
    target_admin: ChatMemberAdministrator | None,
    minutes: int,
    muted_by_id: int,
) -> tuple[bool, str | None]:
    """
    Step 4.1: Save permissions in admin_roles and muted_admins.
    Step 4.2: Demote admin via promoteChatMember with all False.
    Step 4.3: Restrict chat member (mute).
    Step 4.4: Schedule unmute task in APScheduler to restore rights.
    """
    saved_permissions = (
        extract_admin_permissions(target_admin)
        if target_admin
        else {
            "can_manage_chat": True,
            "can_delete_messages": True,
            "can_restrict_members": True,
            "can_invite_users": True,
            "can_pin_messages": True,
        }
    )
    custom_title = target_admin.custom_title if target_admin else None

    # Step 4.2: Demote admin in Telegram chat
    try:
        await asyncio.wait_for(
            bot.promote_chat_member(
                chat_id=chat_id,
                user_id=target_id,
                **DEMOTE_PROMOTION_KWARGS,
            ),
            timeout=8.0,
        )
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        msg = getattr(exc, "message", None) or str(exc)
        logger.warning("Failed to demote admin %s in chat %s: %s", target_id, chat_id, msg)
        return False, (
            f"Не удалось снять права администратора.\n"
            f"Telegram: {msg}\n"
            "Убедитесь, что у бота включено право «Назначение администраторов» "
            "и бот находится выше этого администратора в списке."
        )
    except Exception as exc:
        return False, f"Ошибка снятия прав администратора: {exc}"

    # Step 4.3: Restrict chat member
    until = datetime.now(timezone.utc) + timedelta(minutes=max(1, minutes))
    try:
        await asyncio.wait_for(
            bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_id,
                permissions=MUTE_PERMISSIONS,
                until_date=until,
                use_independent_chat_permissions=True,
            ),
            timeout=8.0,
        )
    except Exception as exc:
        # Rollback: restore admin rights if restrict failed
        try:
            await bot.promote_chat_member(chat_id=chat_id, user_id=target_id, **saved_permissions)
        except Exception:
            pass
        return False, f"Ошибка наложения ограничений: {exc}"

    # Step 4.1: Save permissions in admin_roles and muted_admins
    await admin_roles_service.save_admin_permissions(
        session, target_id, saved_permissions, target_username
    )
    muted_rec = MutedAdmin(
        chat_id=chat_id,
        user_id=target_id,
        username=target_username,
        permissions_json=json.dumps(saved_permissions),
        custom_title=custom_title,
        muted_by_id=muted_by_id,
        unmute_at=until,
        is_active=True,
    )
    session.add(muted_rec)
    await session.commit()

    # Step 4.4: Schedule auto unmute and restore
    job_id = f"unmute_admin_{chat_id}_{target_id}"
    try:
        from services.scheduler import scheduler

        scheduler.add_job(
            job_unmute_admin_auto,
            "date",
            run_date=until,
            args=[chat_id, target_id, target_username],
            id=job_id,
            replace_existing=True,
            coalesce=True,
        )
    except Exception as e:
        logger.exception("Failed to schedule unmute job %s: %s", job_id, e)

    return True, None


async def restore_admin_rights(
    bot: Bot,
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    *,
    reason: str = "manual",
) -> tuple[bool, str | None]:
    """
    Unmutes user, restores saved admin permissions, updates DB record and cancels scheduled job.
    """
    # 1. Unrestrict in chat
    try:
        await asyncio.wait_for(
            bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=UNMUTE_PERMISSIONS,
                use_independent_chat_permissions=True,
            ),
            timeout=8.0,
        )
    except Exception as exc:
        logger.warning("Unrestrict failed for %s in %s: %s", user_id, chat_id, exc)

    # 2. Get saved permissions from admin_roles or muted_admins
    permissions = await admin_roles_service.get_saved_admin_permissions(session, user_id)
    custom_title = None

    result = await session.execute(
        select(MutedAdmin)
        .where(
            MutedAdmin.chat_id == chat_id,
            MutedAdmin.user_id == user_id,
            MutedAdmin.is_active.is_(True),
        )
        .order_by(MutedAdmin.id.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if record:
        custom_title = record.custom_title
        if not permissions and record.permissions_json:
            try:
                permissions = json.loads(record.permissions_json)
            except Exception:
                pass
        record.is_active = False

    if permissions:
        try:
            await asyncio.wait_for(
                bot.promote_chat_member(chat_id=chat_id, user_id=user_id, **permissions),
                timeout=8.0,
            )
            if custom_title:
                try:
                    await bot.set_chat_administrator_custom_title(
                        chat_id=chat_id,
                        user_id=user_id,
                        custom_title=custom_title,
                    )
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("Promote failed when restoring %s in %s: %s", user_id, chat_id, exc)
            return False, f"Ошибка восстановления прав администратора: {exc}"

    await admin_roles_service.clear_saved_admin_permissions(session, user_id)
    await session.commit()

    # Cancel scheduled job if any
    try:
        from services.scheduler import scheduler

        job_id = f"unmute_admin_{chat_id}_{user_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    except Exception:
        pass

    return True, None


async def job_unmute_admin_auto(chat_id: int, user_id: int, username: str | None) -> None:
    from services.scheduler import get_bot

    bot = get_bot()
    if not bot:
        logger.error("Auto unmute job failed: bot instance not available")
        return

    async with async_session() as session:
        ok, err = await restore_admin_rights(bot, session, chat_id, user_id, reason="expired")
        if ok:
            mention = f"@{username}" if username else f"ID {user_id}"
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Мут администратора {mention} завершен. Права полностью восстановлены.",
                )
            except Exception as e:
                logger.warning("Failed to send unmute notification to chat %s: %s", chat_id, e)
        else:
            logger.error("Auto unmute failed for %s in %s: %s", user_id, chat_id, err)


async def restore_pending_muted_admins(bot: Bot) -> None:
    """Check for active muted admins on bot startup and resume schedules or restore immediately."""
    async with async_session() as session:
        result = await session.execute(
            select(MutedAdmin).where(MutedAdmin.is_active.is_(True))
        )
        records = result.scalars().all()
        now = datetime.now(timezone.utc)

        for rec in records:
            unmute_at = rec.unmute_at
            if unmute_at.tzinfo is None:
                unmute_at = unmute_at.replace(tzinfo=timezone.utc)

            if unmute_at <= now:
                await restore_admin_rights(bot, session, rec.chat_id, rec.user_id, reason="expired")
                mention = f"@{rec.username}" if rec.username else f"ID {rec.user_id}"
                try:
                    await bot.send_message(
                        chat_id=rec.chat_id,
                        text=f"Мут администратора {mention} завершен. Права полностью восстановлены.",
                    )
                except Exception:
                    pass
            else:
                job_id = f"unmute_admin_{rec.chat_id}_{rec.user_id}"
                from services.scheduler import scheduler

                try:
                    scheduler.add_job(
                        job_unmute_admin_auto,
                        "date",
                        run_date=unmute_at,
                        args=[rec.chat_id, rec.user_id, rec.username],
                        id=job_id,
                        replace_existing=True,
                        coalesce=True,
                    )
                except Exception as e:
                    logger.exception("Failed to re-register job %s: %s", job_id, e)
        await session.commit()


