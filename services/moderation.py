from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatPermissions
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import User, Warning
from services import users as users_service

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
