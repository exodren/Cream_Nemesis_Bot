from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import Match, Season, SeasonParticipant, User


async def get_current_season(session: AsyncSession) -> int:
    result = await session.execute(
        select(Season).where(Season.is_current.is_(True)).limit(1)
    )
    season = result.scalar_one_or_none()
    if season is not None:
        return season.number
    return get_settings().current_season


async def get_current_season_row(session: AsyncSession) -> Season | None:
    result = await session.execute(
        select(Season).where(Season.is_current.is_(True)).limit(1)
    )
    return result.scalar_one_or_none()


async def list_past_season_numbers(session: AsyncSession) -> list[int]:
    """Archived seasons and other past seasons with confirmed matches (not current)."""
    current = await get_current_season(session)

    archived_result = await session.execute(
        select(Season.number).where(Season.is_archived.is_(True))
    )
    match_seasons_result = await session.execute(
        select(Match.season)
        .where(Match.status == "confirmed", Match.season != current)
        .distinct()
    )

    numbers = set(archived_result.scalars().all()) | set(match_seasons_result.scalars().all())
    return sorted(numbers, reverse=True)


async def is_archived_season(session: AsyncSession, season: int) -> bool:
    row = await session.scalar(select(Season).where(Season.number == season))
    if row is not None:
        return bool(row.is_archived)
    current = await get_current_season(session)
    return season != current


async def ensure_participant(
    session: AsyncSession,
    user_id: int,
    season: int,
    *,
    reactivate: bool = False,
) -> SeasonParticipant:
    result = await session.execute(
        select(SeasonParticipant).where(
            SeasonParticipant.user_id == user_id,
            SeasonParticipant.season == season,
        )
    )
    participant = result.scalar_one_or_none()
    if participant is None:
        participant = SeasonParticipant(user_id=user_id, season=season, is_active=True)
        session.add(participant)
        await session.flush()
        return participant

    if reactivate and not participant.is_active:
        participant.is_active = True
        participant.deactivated_at = None
        await session.flush()
    return participant


async def active_participant_user_ids(session: AsyncSession, season: int) -> set[int]:
    result = await session.execute(
        select(SeasonParticipant.user_id).where(
            SeasonParticipant.season == season,
            SeasonParticipant.is_active.is_(True),
        )
    )
    return set(result.scalars().all())


def _participant_display_name(user: User, tg_id: int) -> str:
    if user.username:
        return f"@{user.username}"
    if user.nickname:
        return user.nickname
    return str(tg_id)


async def deactivate_participant_by_tg_id(
    session: AsyncSession,
    *,
    tg_id: int,
    season: int,
) -> tuple[str, str]:
    """
    Returns (status, display_name).
    status: not_found | deactivated | already_inactive
    """
    user_result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return "not_found", "—"

    display = _participant_display_name(user, tg_id)
    result = await session.execute(
        select(SeasonParticipant).where(
            SeasonParticipant.user_id == user.id,
            SeasonParticipant.season == season,
        )
    )
    participant = result.scalar_one_or_none()
    if participant is not None and not participant.is_active:
        return "already_inactive", display

    now = datetime.now(timezone.utc)
    if participant is None:
        participant = SeasonParticipant(
            user_id=user.id,
            season=season,
            is_active=False,
            deactivated_at=now,
        )
        session.add(participant)
    else:
        participant.is_active = False
        participant.deactivated_at = now
    await session.flush()
    return "deactivated", display


async def end_current_season(session: AsyncSession) -> tuple[bool, str]:
    season = await get_current_season_row(session)
    if season is None:
        return False, "Текущий сезон не найден."

    if season.is_archived:
        return False, f"Сезон #{season.number} уже завершён."

    now = datetime.now(timezone.utc)
    season.is_archived = True
    season.is_current = False
    season.ended_at = now

    await session.execute(
        update(SeasonParticipant)
        .where(
            SeasonParticipant.season == season.number,
            SeasonParticipant.is_active.is_(True),
        )
        .values(is_active=False, deactivated_at=now)
    )
    await session.flush()
    return True, f"Сезон #{season.number} завершён и заархивирован."


async def start_new_season(session: AsyncSession) -> tuple[bool, str, int]:
    current = await get_current_season_row(session)
    if current is not None and not current.is_archived:
        return (
            False,
            f"Сначала завершите сезон #{current.number} («Завершить текущий сезон»).",
            current.number,
        )

    max_number = await session.scalar(select(func.max(Season.number)))
    next_number = (max_number or 0) + 1
    if current is not None and current.number >= next_number:
        next_number = current.number + 1

    new_season = Season(
        number=next_number,
        is_current=True,
        is_archived=False,
    )
    session.add(new_season)
    await session.flush()
    return True, f"Запущен новый сезон #{next_number}.", next_number


async def bootstrap_seasons(session: AsyncSession) -> None:
    """Ensure current season row exists and backfill participants for registered users."""
    settings = get_settings()
    result = await session.execute(select(Season).where(Season.is_current.is_(True)).limit(1))
    current = result.scalar_one_or_none()
    if current is None:
        number = settings.current_season
        existing = await session.scalar(select(Season).where(Season.number == number))
        if existing is None:
            current = Season(number=number, is_current=True, is_archived=False)
            session.add(current)
        else:
            existing.is_current = True
            existing.is_archived = False
            current = existing
        await session.flush()
    elif current.is_archived:
        latest = await session.scalar(
            select(Season).order_by(Season.number.desc()).limit(1)
        )
        if latest is not None and not latest.is_archived:
            await session.execute(update(Season).values(is_current=False))
            latest.is_current = True
            current = latest
            await session.flush()

    season_number = current.number if current else settings.current_season
    users_result = await session.execute(
        select(User).where(User.nickname.is_not(None))
    )
    for user in users_result.scalars().all():
        await ensure_participant(session, user_id=user.id, season=season_number)
