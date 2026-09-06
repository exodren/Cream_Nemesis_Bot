import asyncio
import html
import logging
import random
import re
from typing import Sequence

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

# Pool of 40 diverse emojis for Zazyvala-style tagging
EMOJIS: tuple[str, ...] = (
    "🎭", "🥪", "🚴", "⚽️", "🏀", "🎮", "🔥", "⚡️", "🚀", "🎯",
    "🏆", "🥇", "🥊", "🧩", "🎲", "🎺", "🎸", "🎨", "🎪", "🦁",
    "🐯", "🦅", "🐺", "🍕", "🍔", "🍿", "🍩", "🍣", "🌮", "💣",
    "🛡", "⚔️", "🔱", "💎", "👑", "🔮", "🧿", "🎁", "🎈", "🌟",
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


def chunk_members(members: Sequence[LplRosterMember], batch_size: int = 4) -> list[list[LplRosterMember]]:
    """Split roster list dynamically into batches of batch_size (default 4)."""
    return [list(members[i : i + batch_size]) for i in range(0, len(members), batch_size)]


def format_chunk_emoji_html(chunk: Sequence[LplRosterMember], emoji_offset: int = 0) -> str:
    """Format a chunk of 4 members into an HTML string of emoji links."""
    links: list[str] = []
    for idx, m in enumerate(chunk):
        emoji = EMOJIS[(emoji_offset + idx) % len(EMOJIS)]
        if m.tg_id:
            href = f"tg://user?id={m.tg_id}"
        elif m.username:
            href = f"https://t.me/{m.username}"
        else:
            continue
        links.append(f'<a href="{href}">{emoji}</a>')
    return " ".join(links)


async def run_lpl_call_scenario(
    bot,
    chat_id: int,
    topic_id: int | None,
    members: Sequence[LplRosterMember],
) -> int:
    """
    Executes Zazyvala-style LPL call scenario:
    1. Send default reminder "Напоминание❗️\nОтыграй ЛПЛ❗️"
    2. Loop over 4-member chunks, sending emoji links (sleep 0.4s between to avoid FloodWait)
    3. Send "Призыв окончен."
    """
    if not members:
        return 0

    chunks = chunk_members(members, batch_size=4)

    # Step 1: Start message
    await bot.send_message(
        chat_id=chat_id,
        text=DEFAULT_LPL_REMINDER,
        message_thread_id=topic_id if topic_id else None,
        disable_web_page_preview=True,
    )

    # Step 2: Send chunks
    emoji_offset = 0
    for chunk in chunks:
        await asyncio.sleep(0.4)
        chunk_text = format_chunk_emoji_html(chunk, emoji_offset=emoji_offset)
        emoji_offset += len(chunk)
        if chunk_text:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk_text,
                message_thread_id=topic_id if topic_id else None,
                disable_web_page_preview=True,
            )

    # Step 3: End message
    await asyncio.sleep(0.4)
    await bot.send_message(
        chat_id=chat_id,
        text="Призыв окончен.",
        message_thread_id=topic_id if topic_id else None,
        disable_web_page_preview=True,
    )

    return len(chunks)


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