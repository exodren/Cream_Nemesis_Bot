from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("nickname", name="uq_users_nickname"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    in_queue: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    queue_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    warnings: Mapped[list["Warning"]] = relationship(back_populates="user")
    goals: Mapped[list["Goal"]] = relationship(back_populates="user")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player1_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player2_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    score1: Mapped[int] = mapped_column(Integer)
    score2: Mapped[int] = mapped_column(Integer)
    # pending_confirm | pending_admin | confirmed | rejected
    status: Mapped[str] = mapped_column(String(32), default="pending_confirm", index=True)
    screenshot_file_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    season: Mapped[int] = mapped_column(Integer, default=1, index=True)
    p1_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    p2_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    submitted_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    goals: Mapped[list["Goal"]] = relationship(back_populates="match")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player_name: Mapped[str] = mapped_column(String(128))
    goals_count: Mapped[int] = mapped_column(Integer, default=1)

    match: Mapped["Match"] = relationship(back_populates="goals")
    user: Mapped["User"] = relationship(back_populates="goals")


class Warning(Base):
    __tablename__ = "warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="warnings")
