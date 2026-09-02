from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from services import seasons as seasons_service

router = Router(name="season_manage")
logger = logging.getLogger(__name__)


def _is_admin_id(user_id: int) -> bool:
    return user_id in get_settings().admin_ids


def _season_manage_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Завершить текущий сезон",
                    callback_data="season:end",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Начать новый сезон",
                    callback_data="season:start",
                )
            ],
        ]
    )


async def _season_manage_text(session: AsyncSession) -> str:
    season = await seasons_service.get_current_season_row(session)
    if season is None:
        number = await seasons_service.get_current_season(session)
        return (
            f"<b>Управление сезонами TOVA</b>\n\n"
            f"Текущий сезон: <b>#{number}</b>\n"
            f"Статус: данные из конфигурации"
        )

    status = "активен"
    if season.is_archived:
        status = "завершён (архив)"
    elif not season.is_current:
        status = "не текущий"

    ended = ""
    if season.ended_at:
        ended = f"\nЗавершён: {season.ended_at:%d.%m.%Y %H:%M UTC}"

    return (
        f"<b>Управление сезонами TOVA</b>\n\n"
        f"Текущий сезон: <b>#{season.number}</b>\n"
        f"Статус: {status}{ended}\n\n"
        "• <b>Завершить текущий сезон</b> — архивирует сезон и деактивирует участников.\n"
        "• <b>Начать новый сезон</b> — создаёт новый сезон без участников."
    )


@router.message(Command("season_manage"))
async def cmd_season_manage(message: Message, session: AsyncSession) -> None:
    if not message.from_user or not _is_admin_id(message.from_user.id):
        return

    text = await _season_manage_text(session)
    await message.answer(text, reply_markup=_season_manage_kb())


@router.callback_query(F.data == "season:end")
async def cb_end_season(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or not _is_admin_id(callback.from_user.id):
        await callback.answer("Только для ADMIN_IDS.", show_alert=True)
        return

    ok, result_text = await seasons_service.end_current_season(session)
    await callback.answer(result_text, show_alert=True)

    if callback.message:
        text = await _season_manage_text(session)
        try:
            await callback.message.edit_text(text, reply_markup=_season_manage_kb())
        except Exception:
            logger.exception("Failed to refresh season_manage menu after end")

    logger.info("Season end by admin=%s: ok=%s msg=%s", callback.from_user.id, ok, result_text)


@router.callback_query(F.data == "season:start")
async def cb_start_season(callback: CallbackQuery, session: AsyncSession) -> None:
    if not callback.from_user or not _is_admin_id(callback.from_user.id):
        await callback.answer("Только для ADMIN_IDS.", show_alert=True)
        return

    ok, result_text, new_number = await seasons_service.start_new_season(session)
    await callback.answer(result_text, show_alert=True)

    if callback.message:
        text = await _season_manage_text(session)
        try:
            await callback.message.edit_text(text, reply_markup=_season_manage_kb())
        except Exception:
            logger.exception("Failed to refresh season_manage menu after start")

    logger.info(
        "Season start by admin=%s: ok=%s new=%s msg=%s",
        callback.from_user.id,
        ok,
        new_number,
        result_text,
    )
