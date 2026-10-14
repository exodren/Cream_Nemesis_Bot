from __future__ import annotations

import logging
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Challenge

logger = logging.getLogger(__name__)


async def get_challenge_by_id(
    session: AsyncSession, challenge_id: int
) -> Challenge | None:
    result = await session.execute(
        select(Challenge)
        .options(selectinload(Challenge.challenger), selectinload(Challenge.target))
        .where(Challenge.id == challenge_id)
    )
    return result.scalar_one_or_none()


async def get_active_challenge_for_user(
    session: AsyncSession, user_id: int
) -> Challenge | None:
    """Find any pending challenge where user is either challenger or target."""
    result = await session.execute(
        select(Challenge)
        .options(selectinload(Challenge.challenger), selectinload(Challenge.target))
        .where(
            Challenge.status == "pending",
            or_(
                Challenge.challenger_id == user_id,
                Challenge.target_id == user_id,
            ),
        )
        .order_by(Challenge.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_outgoing_challenge(
    session: AsyncSession, user_id: int
) -> Challenge | None:
    """Find pending challenge initiated by this user."""
    result = await session.execute(
        select(Challenge)
        .options(selectinload(Challenge.challenger), selectinload(Challenge.target))
        .where(
            Challenge.status == "pending",
            Challenge.challenger_id == user_id,
        )
        .order_by(Challenge.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_incoming_challenge(
    session: AsyncSession, user_id: int
) -> Challenge | None:
    """Find pending challenge sent to this user."""
    result = await session.execute(
        select(Challenge)
        .options(selectinload(Challenge.challenger), selectinload(Challenge.target))
        .where(
            Challenge.status == "pending",
            Challenge.target_id == user_id,
        )
        .order_by(Challenge.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_challenge(
    session: AsyncSession,
    challenger_id: int,
    target_id: int,
    chat_id: int,
    message_id: int | None = None,
) -> Challenge:
    challenge = Challenge(
        challenger_id=challenger_id,
        target_id=target_id,
        chat_id=chat_id,
        message_id=message_id,
        status="pending",
    )
    session.add(challenge)
    await session.flush()
    await session.refresh(challenge, ["challenger", "target"])
    return challenge


async def accept_challenge(session: AsyncSession, challenge: Challenge) -> None:
    challenge.status = "accepted"
    await session.flush()


async def decline_challenge(session: AsyncSession, challenge: Challenge) -> None:
    challenge.status = "declined"
    await session.flush()


async def cancel_challenge(session: AsyncSession, challenge: Challenge) -> None:
    challenge.status = "cancelled"
    await session.flush()
