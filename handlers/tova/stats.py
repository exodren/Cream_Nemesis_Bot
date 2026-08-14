from __future__ import annotations

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from keyboards.main import back_only_kb
from services import table_image
from services import tova_stats

router = Router(name="tova_stats")


@router.callback_query(F.data == "menu:tova:season")
async def cb_season_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    season = get_settings().current_season
    summary = await tova_stats.season_summary(session, season)
    text = tova_stats.format_season_text(summary, season)
    if callback.message:
        await callback.message.answer(text, reply_markup=back_only_kb("menu:tova"))


@router.callback_query(F.data == "menu:tova:table")
async def cb_table(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    season = get_settings().current_season
    standings = await tova_stats.build_standings(session, season)
    pages = table_image.render_standings_pages(standings, season=season)
    if not callback.message:
        return
    for idx, buf in enumerate(pages):
        file = BufferedInputFile(buf.getvalue(), filename=f"tova_table_{idx + 1}.png")
        markup = back_only_kb("menu:tova") if idx == len(pages) - 1 else None
        await callback.message.answer_photo(file, reply_markup=markup)


@router.callback_query(F.data == "menu:tova:scorers")
async def cb_scorers(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    season = get_settings().current_season
    scorers = await tova_stats.build_scorers(session, season)
    pages = table_image.render_scorers_pages(scorers, season=season)
    if not callback.message:
        return
    for idx, buf in enumerate(pages):
        file = BufferedInputFile(buf.getvalue(), filename=f"tova_scorers_{idx + 1}.png")
        markup = back_only_kb("menu:tova") if idx == len(pages) - 1 else None
        await callback.message.answer_photo(file, reply_markup=markup)


@router.callback_query(F.data == "menu:tova:stats")
async def cb_personal_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    season = get_settings().current_season
    stats = await tova_stats.get_personal_stats(
        session,
        tg_id=callback.from_user.id,
        season=season,
    )
    if stats is None:
        text = (
            "Сначала зарегистрируйте никнейм:\n"
            "TOVA → Регистрация → Изменить никнейм"
        )
    else:
        best = await tova_stats.get_best_scorer_for_user(
            session,
            user_id=stats.user_id,
            season=season,
        )
        text = tova_stats.format_personal_text(stats, season=season, best_scorer=best)

    if callback.message:
        await callback.message.answer(text, reply_markup=back_only_kb("menu:tova"))
