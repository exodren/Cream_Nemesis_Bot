from __future__ import annotations

import logging

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Match
from keyboards.tova import tova_admin_review_kb
from services import matches as matches_service
from services import users as users_service

logger = logging.getLogger(__name__)


async def get_pending_admin_matches(session: AsyncSession) -> list[Match]:
    result = await session.execute(
        select(Match)
        .where(Match.status == "pending_admin")
        .order_by(Match.id)
    )
    return list(result.scalars().all())


async def notify_tova_reviewers(
    bot: Bot,
    session: AsyncSession,
    match: Match,
    *,
    reminder: bool = False,
) -> int:
    """Send TOVA admin review card. Returns count of successful deliveries."""
    p1 = await matches_service.get_user(session, match.player1_id)
    p2 = await matches_service.get_user(session, match.player2_id)
    if p1 is None or p2 is None:
        logger.warning("TOVA match=%s: player row missing", match.id)
        return 0

    goals = await matches_service.load_match_goals(session, match.id)
    card = matches_service.format_match_card(match, p1, p2, goals)
    if reminder:
        header = (
            "<b>Матч TOVA ожидает проверки</b>\n"
            "(напоминание — бот перезапущен или сменился модератор)\n\n"
        )
    else:
        header = "<b>Новый результат TOVA на проверку!</b>\n\n"
    admin_text = header + card
    markup = tova_admin_review_kb(match.id)

    reviewer_ids = await users_service.resolve_tova_reviewer_ids(session)
    if not reviewer_ids:
        logger.warning(
            "TOVA pending_admin match=%s: no TOVA_ADMIN_ID / ADMINS_TOVA recipient",
            match.id,
        )
        return 0

    sent = 0
    for admin_id in reviewer_ids:
        try:
            if match.screenshot_file_id:
                await bot.send_photo(
                    admin_id,
                    photo=match.screenshot_file_id,
                    caption=admin_text,
                    reply_markup=markup,
                )
            else:
                await bot.send_message(
                    admin_id,
                    admin_text,
                    reply_markup=markup,
                )
            sent += 1
        except Exception:
            logger.exception("Failed to send TOVA card to %s (match=%s)", admin_id, match.id)
    return sent


async def resend_pending_admin_cards(bot: Bot, session: AsyncSession) -> tuple[int, int]:
    """Resend all pending_admin matches. Returns (match_count, delivery_count)."""
    matches = await get_pending_admin_matches(session)
    deliveries = 0
    for match in matches:
        deliveries += await notify_tova_reviewers(
            bot,
            session,
            match,
            reminder=True,
        )
    return len(matches), deliveries
