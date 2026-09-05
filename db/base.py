from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

_settings = get_settings()


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_parent(database_url: str) -> None:
    if "sqlite" not in database_url:
        return
    # sqlite+aiosqlite:///./data/bot.db or absolute path
    raw = database_url.split(":///", 1)[-1]
    db_path = Path(raw)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent(_settings.database_url)

engine: AsyncEngine = create_async_engine(
    _settings.database_url,
    echo=False,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


async def _sqlite_columns(conn, table: str) -> set[str]:
    rows = (await conn.execute(text(f"PRAGMA table_info({table})"))).mappings().all()
    return {str(row["name"]) for row in rows}


async def migrate_schema(conn) -> None:
    """Add missing columns on existing SQLite DBs (create_all does not ALTER)."""
    tables = {
        row[0]
        for row in (
            await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        ).all()
    }
    if "warnings" not in tables:
        return

    columns = await _sqlite_columns(conn, "warnings")
    if "username" not in columns:
        await conn.execute(text("ALTER TABLE warnings ADD COLUMN username VARCHAR(64)"))
    if "league_nickname" not in columns:
        await conn.execute(
            text("ALTER TABLE warnings ADD COLUMN league_nickname VARCHAR(64)")
        )


async def init_db() -> None:
    from db import models  # noqa: F401 — register models
    from services.seasons import bootstrap_seasons

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await migrate_schema(conn)
        # Explicit WAL ensure after create (in addition to connect hook)
        await conn.execute(text("PRAGMA journal_mode=WAL;"))
        await conn.execute(text("PRAGMA busy_timeout=5000;"))

    async with async_session() as session:
        await bootstrap_seasons(session)
        await session.commit()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
