from __future__ import annotations

import re

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import Goal, Match, User
from services.users import get_user_by_nickname

RESULT_RE = re.compile(
    r"^/result_tova(?:@\w+)?\s+(\S+)\s+(\d+)\s*:\s*(\d+)\s+(\S+)\s*$",
    re.IGNORECASE,
)
SCORER_ITEM_RE = re.compile(r"^\s*(.+?)(?:\s*\((\d+)\))?\s*$")


def parse_result_command(text: str) -> tuple[str, int, int, str] | None:
    match = RESULT_RE.match(text.strip())
    if not match:
        return None
    nick1, s1, s2, nick2 = match.groups()
    return nick1, int(s1), int(s2), nick2


def parse_scorers_line(line: str) -> tuple[str, list[tuple[str, int]]] | None:
    """
    Formats:
      nick — C. Ronaldo (5), Mbappé (3)
      nick - Messi, Neymar Jr.
    """
    if "—" in line:
        nick_part, scorers_part = line.split("—", 1)
    elif " - " in line:
        nick_part, scorers_part = line.split(" - ", 1)
    elif "-" in line:
        nick_part, scorers_part = line.split("-", 1)
    else:
        return None

    nickname = nick_part.strip()
    if not nickname:
        return None

    items: list[tuple[str, int]] = []
    for raw in scorers_part.split(","):
        raw = raw.strip()
        if not raw:
            continue
        m = SCORER_ITEM_RE.match(raw)
        if not m:
            continue
        name = m.group(1).strip()
        count = int(m.group(2)) if m.group(2) else 1
        if name and count > 0:
            items.append((name, count))
    return nickname, items


async def create_pending_match(
    session: AsyncSession,
    *,
    submitter: User,
    nick1: str,
    score1: int,
    score2: int,
    nick2: str,
    scorers_p1: list[tuple[str, int]],
    scorers_p2: list[tuple[str, int]],
    screenshot_file_id: str,
) -> tuple[Match | None, str]:
    if nick1.lower() == nick2.lower():
        return None, "Никнеймы участников должны отличаться."

    p1 = await get_user_by_nickname(session, nick1)
    p2 = await get_user_by_nickname(session, nick2)
    if p1 is None or p2 is None:
        missing = nick1 if p1 is None else nick2
        if p1 is None and p2 is None:
            return None, f"Игроки не найдены: {nick1}, {nick2}. Оба должны зарегистрироваться в TOVA."
        return None, f"Игрок с ником <b>{missing}</b> не найден. Нужна регистрация в TOVA."

    if submitter.id not in {p1.id, p2.id}:
        return None, "Вы можете отправить результат только матча с вашим участием."

    # Block duplicate open matches between the same pair
    open_statuses = ("pending_confirm", "pending_admin")
    dup = await session.execute(
        select(Match).where(
            Match.status.in_(open_statuses),
            or_(
                and_(Match.player1_id == p1.id, Match.player2_id == p2.id),
                and_(Match.player1_id == p2.id, Match.player2_id == p1.id),
            ),
        ).limit(1)
    )
    existing = dup.scalar_one_or_none()
    if existing is not None:
        return None, (
            f"Уже есть незакрытый матч #{existing.id} "
            f"(статус: {existing.status}). Дождитесь подтверждения или отклонения."
        )

    goals_sum_1 = sum(c for _, c in scorers_p1)
    goals_sum_2 = sum(c for _, c in scorers_p2)
    if goals_sum_1 != score1 or goals_sum_2 != score2:
        return None, (
            "Сумма голов бомбардиров не совпадает со счётом.\n"
            f"Ожидалось {score1}:{score2}, получено {goals_sum_1}:{goals_sum_2}."
        )

    settings = get_settings()
    match = Match(
        player1_id=p1.id,
        player2_id=p2.id,
        score1=score1,
        score2=score2,
        status="pending_confirm",
        screenshot_file_id=screenshot_file_id,
        season=settings.current_season,
        submitted_by_id=submitter.id,
        p1_confirmed=submitter.id == p1.id,
        p2_confirmed=submitter.id == p2.id,
    )
    session.add(match)
    await session.flush()

    for name, count in scorers_p1:
        session.add(
            Goal(match_id=match.id, user_id=p1.id, player_name=name, goals_count=count)
        )
    for name, count in scorers_p2:
        session.add(
            Goal(match_id=match.id, user_id=p2.id, player_name=name, goals_count=count)
        )
    await session.flush()
    return match, "ok"


async def get_match(session: AsyncSession, match_id: int) -> Match | None:
    result = await session.execute(select(Match).where(Match.id == match_id))
    return result.scalar_one_or_none()


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def find_open_match_for_user(session: AsyncSession, user: User) -> Match | None:
    open_statuses = ("pending_confirm", "pending_admin")
    result = await session.execute(
        select(Match)
        .where(
            Match.status.in_(open_statuses),
            or_(Match.player1_id == user.id, Match.player2_id == user.id),
        )
        .order_by(Match.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def find_open_match_between(
    session: AsyncSession,
    user_a: User,
    user_b: User,
) -> Match | None:
    open_statuses = ("pending_confirm", "pending_admin")
    result = await session.execute(
        select(Match)
        .where(
            Match.status.in_(open_statuses),
            or_(
                and_(Match.player1_id == user_a.id, Match.player2_id == user_b.id),
                and_(Match.player1_id == user_b.id, Match.player2_id == user_a.id),
            ),
        )
        .order_by(Match.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def confirm_match_by_user(
    session: AsyncSession,
    match: Match,
    user: User,
    *,
    accept: bool,
) -> tuple[str, Match]:
    if match.status != "pending_confirm":
        return "already_closed", match

    if user.id not in {match.player1_id, match.player2_id}:
        return "not_participant", match

    if not accept:
        match.status = "rejected"
        await session.flush()
        return "rejected", match

    if user.id == match.player1_id:
        match.p1_confirmed = True
    else:
        match.p2_confirmed = True

    if match.p1_confirmed and match.p2_confirmed:
        match.status = "pending_admin"
        await session.flush()
        return "pending_admin", match

    await session.flush()
    return "waiting_other", match


async def admin_decide_match(
    session: AsyncSession,
    match: Match,
    *,
    approve: bool,
) -> tuple[str, Match]:
    if match.status != "pending_admin":
        return "wrong_status", match
    match.status = "confirmed" if approve else "rejected"
    await session.flush()
    return match.status, match


def format_match_card(match: Match, p1: User, p2: User, goals: list[Goal] | None = None) -> str:
    lines = [
        f"<b>Матч TOVA #{match.id}</b>",
        f"{p1.nickname} {match.score1}:{match.score2} {p2.nickname}",
        f"Статус: <code>{match.status}</code>",
        f"Сезон: {match.season}",
    ]
    if goals:
        lines.append("")
        lines.append("<b>Бомбардиры:</b>")
        for g in goals:
            owner = p1.nickname if g.user_id == p1.id else p2.nickname
            lines.append(f"• {g.player_name} ({g.goals_count}) — {owner}")
    return "\n".join(lines)


async def load_match_goals(session: AsyncSession, match_id: int) -> list[Goal]:
    result = await session.execute(select(Goal).where(Goal.match_id == match_id))
    return list(result.scalars().all())
