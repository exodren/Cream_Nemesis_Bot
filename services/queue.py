from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User

QUEUE_TTL = timedelta(minutes=15)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def leave_queue(session: AsyncSession, user: User) -> bool:
    was_in_queue = user.in_queue
    user.in_queue = False
    user.queue_at = None
    await session.flush()
    return was_in_queue


async def enqueue_or_match(
    session: AsyncSession,
    user: User,
) -> tuple[str, User | None]:
    """
    Returns (status, opponent).
    status: need_nickname | already_queued | waiting | matched
    """
    if not user.nickname:
        return "need_nickname", None

    if user.in_queue and user.queue_at:
        queued_at = user.queue_at
        if queued_at.tzinfo is None:
            queued_at = queued_at.replace(tzinfo=timezone.utc)
        if _utcnow() - queued_at < QUEUE_TTL:
            return "already_queued", None
        await leave_queue(session, user)

    # Find another waiting player (not self, with nickname, not expired)
    cutoff = _utcnow() - QUEUE_TTL
    result = await session.execute(
        select(User)
        .where(
            User.in_queue.is_(True),
            User.id != user.id,
            User.nickname.is_not(None),
            User.is_banned.is_(False),
            User.queue_at.is_not(None),
            User.queue_at >= cutoff,
        )
        .order_by(User.queue_at.asc())
        .limit(1)
    )
    opponent = result.scalar_one_or_none()
    if opponent is None:
        user.in_queue = True
        user.queue_at = _utcnow()
        await session.flush()
        return "waiting", None

    await leave_queue(session, opponent)
    await leave_queue(session, user)
    return "matched", opponent
