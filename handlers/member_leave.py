from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.filters.chat_member_updated import LEAVE_TRANSITION, ChatMemberUpdatedFilter
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from services import seasons as seasons_service
from services import users as users_service

router = Router(name="member_leave")
logger = logging.getLogger(__name__)


def _leave_alert_text(
    *,
    first_name: str | None,
    last_name: str | None,
    username: str | None,
    user_id: int,
    season: int,
) -> str:
    full_name = f"{first_name or ''} {last_name or ''}".strip() or "—"
    username_display = f"@{username}" if username else "—"
    return (
        "⚠️ <b>Участник покинул чат Лиги!</b>\n"
        f"• <b>Имя:</b> {html.escape(full_name)}\n"
        f"• <b>Юзернейм:</b> {html.escape(username_display)}\n"
        f"• <b>ID:</b> <code>{user_id}</code>\n"
        f"• <b>Сезон:</b> {season}"
    )


def _leave_alert_kb(tg_user_id: int, season: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Снять с турнира (Удалить из БД)",
                    callback_data=f"leave:kick:{tg_user_id}:{season}",
                )
            ]
        ]
    )


@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_member_left(event: ChatMemberUpdated, session: AsyncSession) -> None:
    settings = get_settings()
    if not settings.main_chat_id or event.chat.id != settings.main_chat_id:
        return
    if event.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return

    user = event.new_chat_member.user
    if user.is_bot:
        return

    season = await seasons_service.get_current_season(session)
    text = _leave_alert_text(
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        user_id=user.id,
        season=season,
    )
    markup = _leave_alert_kb(user.id, season)

    admin_ids = await users_service.resolve_admin_ids(session)
    if not admin_ids:
        logger.warning("Member left user=%s: no admin recipients configured", user.id)
        return

    sent = 0
    for admin_id in admin_ids:
        try:
            await event.bot.send_message(admin_id, text, reply_markup=markup)
            sent += 1
        except Exception:
            logger.exception(
                "Failed to send leave alert to admin=%s for user=%s",
                admin_id,
                user.id,
            )

    logger.info(
        "Leave alert for user=%s in chat=%s: sent %d/%d",
        user.id,
        event.chat.id,
        sent,
        len(admin_ids),
    )


@router.callback_query(F.data.startswith("leave:kick:"))
async def cb_kick_from_season(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or not get_settings().is_admin(
        callback.from_user.id,
        callback.from_user.username,
    ):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    try:
        tg_id = int(parts[2])
        season = int(parts[3])
    except ValueError:
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    status, username = await seasons_service.deactivate_participant_by_tg_id(
        session,
        tg_id=tg_id,
        season=season,
    )
    if status == "not_found":
        await callback.answer("Пользователь не найден в БД.", show_alert=True)
        return

    if status == "already_inactive":
        await callback.answer("Игрок уже исключён из сезона", show_alert=True)
        if callback.message:
            done_text = (
                f"ℹ️ Игрок {html.escape(username)} уже вычеркнут "
                f"из базы сезона {season}"
            )
            try:
                await callback.message.edit_text(done_text)
            except Exception:
                logger.exception(
                    "Failed to edit leave alert (already inactive) user=%s season=%s",
                    tg_id,
                    season,
                )
        return

    await callback.answer("Игрок исключен из сезона", show_alert=True)

    if callback.message:
        done_text = (
            f"✅ Игрок {html.escape(username)} вычеркнут из базы сезона {season}"
        )
        try:
            await callback.message.edit_text(done_text)
        except Exception:
            logger.exception(
                "Failed to edit leave alert message for user=%s season=%s",
                tg_id,
                season,
            )
