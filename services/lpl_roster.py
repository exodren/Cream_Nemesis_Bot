from __future__ import annotations

import html
import logging
import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LplRosterMember, User

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"@[\w\d_]+", re.UNICODE)

# Zero-width space — invisible tag carrier for push notifications.
_ZWSP = "\u200b"

DEFAULT_LPL_REMINDER = (
    "Напоминание❗️\n"
    "Отыграй ЛПЛ❗️"
)


def parse_usernames(text: str) -> list[str]:
    """Extract unique @usernames from free-form roster text (order preserved)."""
    found = USERNAME_RE.findall(text or "")
    seen: set[str] = set()
    result: list[str] = []
    for raw in found:
        name = raw.lstrip("@").lower()
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


async def replace_roster(session: AsyncSession, usernames: list[str]) -> int:
    """Replace full LPL roster. Resolves tg_id from users table when possible."""
    await session.execute(delete(LplRosterMember))
    if not usernames:
        await session.flush()
        return 0

    result = await session.execute(
        select(User).where(User.username.in_(usernames))
    )
    by_name = {
        (u.username or "").lower(): u
        for u in result.scalars().all()
        if u.username
    }

    for name in usernames:
        user = by_name.get(name)
        session.add(
            LplRosterMember(
                username=name,
                tg_id=user.tg_id if user else None,
            )
        )
    await session.flush()
    return len(usernames)


async def clear_roster(session: AsyncSession) -> int:
    result = await session.execute(select(LplRosterMember))
    members = list(result.scalars().all())
    count = len(members)
    await session.execute(delete(LplRosterMember))
    await session.flush()
    return count


async def list_roster(session: AsyncSession) -> list[LplRosterMember]:
    result = await session.execute(
        select(LplRosterMember).order_by(LplRosterMember.username)
    )
    return list(result.scalars().all())


def format_roster_text(members: list[LplRosterMember]) -> str:
    if not members:
        return "Состав ЛПЛ пуст. Загрузите список через админ-панель."
    lines = [f"<b>Состав ЛПЛ</b> ({len(members)}):", ""]
    for m in members:
        tag = f"@{html.escape(m.username)}"
        resolved = " · id есть" if m.tg_id else ""
        lines.append(f"• {tag}{resolved}")
    return "\n".join(lines)


def build_hidden_tags(members: list[LplRosterMember]) -> str:
    """
    Zavodila-style silent mentions: each member gets a push via a hidden HTML link,
    without flooding the chat with a wall of @usernames.
    """
    chunks: list[str] = []
    for m in members:
        if m.tg_id:
            href = f"tg://user?id={m.tg_id}"
        else:
            href = f"https://t.me/{m.username}"
        chunks.append(f'<a href="{href}">{_ZWSP}</a>')
    return "".join(chunks)


def build_lpl_reminder_html(
    members: list[LplRosterMember],
    *,
    body: str = DEFAULT_LPL_REMINDER,
) -> str:
    tags = build_hidden_tags(members)
    if not tags:
        return body
    return f"{body}\n{tags}"


async def resolve_missing_tg_ids(session: AsyncSession, bot) -> int:
    """Try Bot API getChat(@username) for roster rows without tg_id."""
    members = await list_roster(session)
    fixed = 0
    for m in members:
        if m.tg_id:
            continue
        try:
            chat = await bot.get_chat(f"@{m.username}")
            if chat and chat.id:
                m.tg_id = chat.id
                fixed += 1
        except Exception:
            logger.debug("Cannot resolve tg_id for @%s", m.username, exc_info=True)
    if fixed:
        await session.flush()
    return fixed