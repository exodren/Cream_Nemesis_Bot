from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


async def get_or_create_user(
    session: AsyncSession,
    *,
    tg_id: int,
    username: str | None = None,
) -> User:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(tg_id=tg_id, username=username)
        session.add(user)
        await session.flush()
        return user

    if username and user.username != username:
        user.username = username
    return user


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    clean = username.lstrip("@").lower()
    result = await session.execute(
        select(User).where(func.lower(User.username) == clean)
    )
    return result.scalar_one_or_none()


async def resolve_tova_reviewer_ids(session: AsyncSession) -> list[int]:
    """Numeric Telegram IDs that receive TOVA approve cards (Zarif / TOVA_ADMIN_ID)."""
    from config import get_settings

    settings = get_settings()
    ids: set[int] = set(settings.tova_admin_ids)
    for uname in settings.league_admins.get("tova", []):
        user = await get_user_by_username(session, uname)
        if user:
            ids.add(user.tg_id)
    return sorted(ids)


async def get_user_by_nickname(session: AsyncSession, nickname: str) -> User | None:
    result = await session.execute(
        select(User).where(func.lower(User.nickname) == nickname.lower())
    )
    return result.scalar_one_or_none()


def _nickname_error(nickname: str) -> str | None:
    cleaned = nickname.strip()
    if not cleaned:
        return "Никнейм не может быть пустым."
    if len(cleaned) > 64:
        return "Никнейм слишком длинный (макс. 64 символа)."
    if any(ch.isspace() for ch in cleaned):
        return "Никнейм не должен содержать пробелы."
    return None


async def set_nickname(
    session: AsyncSession,
    user: User,
    nickname: str,
) -> tuple[bool, str]:
    """Rewrite nickname in DB only after every check passes. Invalid input leaves the old value."""
    err = _nickname_error(nickname)
    if err:
        return False, err

    cleaned = nickname.strip()
    if user.nickname == cleaned:
        return True, f"Никнейм уже установлен: <b>{cleaned}</b>"

    existing = await get_user_by_nickname(session, cleaned)
    if existing is not None and existing.id != user.id:
        return False, "Этот никнейм уже занят. Выберите другой."

    try:
        async with session.begin_nested():
            await session.execute(
                update(User).where(User.id == user.id).values(nickname=cleaned)
            )
            await session.flush()
    except IntegrityError:
        await session.refresh(user, attribute_names=["nickname"])
        return False, "Этот никнейм уже занят. Выберите другой."

    user.nickname = cleaned
    return True, f"Никнейм сохранён: <b>{cleaned}</b>"


async def clear_nickname(session: AsyncSession, user: User) -> str:
    if not user.nickname:
        return "У вас не задан никнейм."
    old = user.nickname
    user.nickname = None
    await session.flush()
    return f"Никнейм <b>{old}</b> удалён."
