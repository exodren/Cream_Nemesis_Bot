from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Goal, Match, SeasonParticipant, User
from services.seasons import active_participant_user_ids


@dataclass
class PlayerStats:
    user_id: int
    nickname: str
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    clean_sheets: int = 0

    @property
    def goal_diff(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def goals_display(self) -> str:
        return f"{self.goals_for}:{self.goals_against}"


@dataclass
class ScorerStats:
    player_name: str
    nickname: str
    goals: int


@dataclass
class SeasonSummary:
    leaders_points: PlayerStats | None = None
    leaders_clean_sheets: PlayerStats | None = None
    best_scorer: ScorerStats | None = None
    top5: list[PlayerStats] = field(default_factory=list)
    total_players: int = 0
    total_matches: int = 0


async def _confirmed_matches(session: AsyncSession, season: int) -> list[Match]:
    result = await session.execute(
        select(Match).where(Match.status == "confirmed", Match.season == season)
    )
    return list(result.scalars().all())


async def _users_map(session: AsyncSession, user_ids: set[int]) -> dict[int, User]:
    if not user_ids:
        return {}
    result = await session.execute(select(User).where(User.id.in_(user_ids)))
    return {u.id: u for u in result.scalars().all()}


def _apply_match(stats: dict[int, PlayerStats], match: Match, users: dict[int, User]) -> None:
    for uid in (match.player1_id, match.player2_id):
        if uid not in stats:
            user = users[uid]
            stats[uid] = PlayerStats(user_id=uid, nickname=user.nickname or f"id:{uid}")

    s1 = stats[match.player1_id]
    s2 = stats[match.player2_id]
    s1.played += 1
    s2.played += 1
    s1.goals_for += match.score1
    s1.goals_against += match.score2
    s2.goals_for += match.score2
    s2.goals_against += match.score1

    if match.score2 == 0:
        s1.clean_sheets += 1
    if match.score1 == 0:
        s2.clean_sheets += 1

    if match.score1 > match.score2:
        s1.wins += 1
        s1.points += 3
        s2.losses += 1
    elif match.score1 < match.score2:
        s2.wins += 1
        s2.points += 3
        s1.losses += 1
    else:
        s1.draws += 1
        s2.draws += 1
        s1.points += 1
        s2.points += 1


async def build_standings(
    session: AsyncSession,
    season: int,
    *,
    historical: bool = False,
) -> list[PlayerStats]:
    active_ids: set[int] | None = None
    if not historical:
        active_ids = await active_participant_user_ids(session, season)

    matches = await _confirmed_matches(session, season)
    user_ids = {m.player1_id for m in matches} | {m.player2_id for m in matches}
    if active_ids is not None:
        user_ids &= active_ids
    users = await _users_map(session, user_ids)
    stats: dict[int, PlayerStats] = {}
    for match in matches:
        if active_ids is not None and (
            match.player1_id not in active_ids or match.player2_id not in active_ids
        ):
            continue
        _apply_match(stats, match, users)

    return sorted(
        stats.values(),
        key=lambda s: (s.points, s.goal_diff, s.goals_for, s.wins),
        reverse=True,
    )


async def build_scorers(
    session: AsyncSession,
    season: int,
    *,
    historical: bool = False,
) -> list[ScorerStats]:
    active_ids: set[int] | None = None
    if not historical:
        active_ids = await active_participant_user_ids(session, season)
        if not active_ids:
            return []

    query = (
        select(
            Goal.player_name,
            User.nickname,
            func.sum(Goal.goals_count).label("goals"),
        )
        .join(Match, Match.id == Goal.match_id)
        .join(User, User.id == Goal.user_id)
        .where(Match.status == "confirmed", Match.season == season)
    )
    if active_ids is not None:
        query = query.where(Goal.user_id.in_(active_ids))

    result = await session.execute(
        query.group_by(Goal.player_name, User.nickname)
        .order_by(func.sum(Goal.goals_count).desc(), Goal.player_name.asc())
    )
    rows = result.all()
    return [
        ScorerStats(player_name=r.player_name, nickname=r.nickname or "—", goals=int(r.goals))
        for r in rows
    ]


async def get_personal_stats(
    session: AsyncSession,
    *,
    tg_id: int,
    season: int,
) -> PlayerStats | None:
    user_result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.nickname:
        return None

    standings = await build_standings(session, season)
    for row in standings:
        if row.user_id == user.id:
            return row
    return PlayerStats(user_id=user.id, nickname=user.nickname)


async def get_best_scorer_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    season: int,
) -> ScorerStats | None:
    result = await session.execute(
        select(
            Goal.player_name,
            User.nickname,
            func.sum(Goal.goals_count).label("goals"),
        )
        .join(Match, Match.id == Goal.match_id)
        .join(User, User.id == Goal.user_id)
        .where(
            Match.status == "confirmed",
            Match.season == season,
            Goal.user_id == user_id,
        )
        .group_by(Goal.player_name, User.nickname)
        .order_by(func.sum(Goal.goals_count).desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    return ScorerStats(
        player_name=row.player_name,
        nickname=row.nickname or "—",
        goals=int(row.goals),
    )


async def season_summary(
    session: AsyncSession,
    season: int,
    *,
    historical: bool = False,
) -> SeasonSummary:
    standings = await build_standings(session, season, historical=historical)
    scorers = await build_scorers(session, season, historical=historical)
    matches = await _confirmed_matches(session, season)

    if historical:
        total_players = len(standings)
    else:
        registered = await session.execute(
            select(func.count())
            .select_from(SeasonParticipant)
            .join(User, User.id == SeasonParticipant.user_id)
            .where(
                SeasonParticipant.season == season,
                SeasonParticipant.is_active.is_(True),
                User.nickname.is_not(None),
            )
        )
        total_players = int(registered.scalar() or 0)

    summary = SeasonSummary(
        top5=standings[:5],
        total_players=total_players,
        total_matches=len(matches),
        best_scorer=scorers[0] if scorers else None,
    )
    if standings:
        summary.leaders_points = standings[0]
        summary.leaders_clean_sheets = max(standings, key=lambda s: s.clean_sheets)
    return summary


def format_season_text(
    summary: SeasonSummary,
    season: int,
    *,
    archived: bool = False,
) -> str:
    suffix = " (архив)" if archived else ""
    lines = [f"<b>Статистика сезона TOVA #{season}</b>{suffix}", "", "<b>Лидеры сезона:</b>"]
    if summary.leaders_points:
        p = summary.leaders_points
        lines.append(
            f"Лидер по очкам: <b>{p.nickname}</b> — {p.points} очков | {p.played} матчей"
        )
    else:
        lines.append("Лидер по очкам: пока нет данных")

    if summary.leaders_clean_sheets and summary.leaders_clean_sheets.clean_sheets > 0:
        c = summary.leaders_clean_sheets
        lines.append(
            f"Больше всего сухих матчей: <b>{c.nickname}</b> — {c.clean_sheets}"
        )
    else:
        lines.append("Больше всего сухих матчей: пока нет данных")

    if summary.best_scorer:
        s = summary.best_scorer
        lines.append(
            f"Лучший бомбардир: <b>{s.player_name}</b> ({s.nickname}) — {s.goals} голов"
        )
    else:
        lines.append("Лучший бомбардир: пока нет данных")

    lines.extend(["", "<b>ТОП-5 игроков по очкам:</b>"])
    if summary.top5:
        for i, row in enumerate(summary.top5, start=1):
            lines.append(f"{i}. {row.nickname} — {row.points}")
    else:
        lines.append("Пока пусто")

    lines.extend(
        [
            "",
            "<b>Общая статистика сезона:</b>",
            f"Всего игроков: {summary.total_players}",
            f"Количество матчей: {summary.total_matches}",
        ]
    )
    return "\n".join(lines)


def format_personal_text(
    stats: PlayerStats,
    *,
    season: int,
    best_scorer: ScorerStats | None,
) -> str:
    best = (
        f"{best_scorer.player_name} — {best_scorer.goals}"
        if best_scorer
        else "—"
    )
    return (
        f"<b>Личная статистика TOVA</b> (сезон {season})\n"
        f"Никнейм: <b>{stats.nickname}</b>\n\n"
        f"TOV сыграно: {stats.played}\n"
        f"Очки: {stats.points}\n"
        f"Победы: {stats.wins}\n"
        f"Ничьи: {stats.draws}\n"
        f"Поражения: {stats.losses}\n"
        f"Забито / Пропущено: {stats.goals_display}\n"
        f"Разница голов: {stats.goal_diff:+d}\n"
        f"Лучший бомбардир: {best}\n"
        f"Сухие матчи: {stats.clean_sheets}"
    )
