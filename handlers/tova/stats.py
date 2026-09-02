from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from handlers.callback_ui import edit_screen, send_photo_pages
from keyboards.main import back_only_kb
from keyboards.tova import tova_archive_list_kb, tova_archive_season_kb
from services import seasons as seasons_service
from services import table_image
from services import tova_stats

router = Router(name="tova_stats")


@router.callback_query(F.data == "menu:tova:season")
async def cb_season_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    season = await seasons_service.get_current_season(session)
    summary = await tova_stats.season_summary(session, season)
    text = tova_stats.format_season_text(summary, season)
    await edit_screen(callback, text, back_only_kb("menu:tova"))


@router.callback_query(F.data == "menu:tova:table")
async def cb_table(callback: CallbackQuery, session: AsyncSession) -> None:
    season = await seasons_service.get_current_season(session)
    standings = await tova_stats.build_standings(session, season)
    pages = table_image.render_standings_pages(standings, season=season)
    await send_photo_pages(
        callback,
        pages,
        filename_prefix="tova_table",
        final_markup=back_only_kb("menu:tova"),
    )


@router.callback_query(F.data == "menu:tova:scorers")
async def cb_scorers(callback: CallbackQuery, session: AsyncSession) -> None:
    season = await seasons_service.get_current_season(session)
    scorers = await tova_stats.build_scorers(session, season)
    pages = table_image.render_scorers_pages(scorers, season=season)
    await send_photo_pages(
        callback,
        pages,
        filename_prefix="tova_scorers",
        final_markup=back_only_kb("menu:tova"),
    )


@router.callback_query(F.data == "menu:tova:stats")
async def cb_personal_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    season = await seasons_service.get_current_season(session)
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

    await edit_screen(callback, text, back_only_kb("menu:tova"))


@router.callback_query(F.data == "menu:tova:archive")
async def cb_archive_list(callback: CallbackQuery, session: AsyncSession) -> None:
    seasons = await seasons_service.list_past_season_numbers(session)
    if not seasons:
        await edit_screen(
            callback,
            "Архив сезонов пуст.",
            back_only_kb("menu:tova"),
        )
        return
    await edit_screen(
        callback,
        "<b>Архив сезонов TOVA</b>\nВыберите сезон:",
        tova_archive_list_kb(seasons),
    )


@router.callback_query(F.data.startswith("menu:tova:archive:"))
async def cb_archive_season(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) < 4:
        await callback.answer()
        return

    try:
        season = int(parts[3])
    except ValueError:
        await callback.answer()
        return

    if len(parts) == 4:
        await edit_screen(
            callback,
            f"<b>Сезон TOVA #{season}</b> (архив)\nЧто показать?",
            tova_archive_season_kb(season),
        )
        return

    if len(parts) != 5:
        await callback.answer()
        return

    action = parts[4]
    archived = await seasons_service.is_archived_season(session, season)

    if action == "stats":
        summary = await tova_stats.season_summary(session, season, historical=True)
        text = tova_stats.format_season_text(summary, season, archived=archived)
        await edit_screen(callback, text, tova_archive_season_kb(season))
        return

    if action == "table":
        standings = await tova_stats.build_standings(session, season, historical=True)
        pages = table_image.render_standings_pages(standings, season=season)
        await send_photo_pages(
            callback,
            pages,
            filename_prefix=f"tova_archive_table_{season}",
            final_markup=tova_archive_season_kb(season),
        )
        return

    if action == "scorers":
        scorers = await tova_stats.build_scorers(session, season, historical=True)
        pages = table_image.render_scorers_pages(scorers, season=season)
        await send_photo_pages(
            callback,
            pages,
            filename_prefix=f"tova_archive_scorers_{season}",
            final_markup=tova_archive_season_kb(season),
        )
        return

    await callback.answer()
