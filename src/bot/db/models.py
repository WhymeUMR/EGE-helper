from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    username: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subjects: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    weekly_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Problem(Base):
    """Карточка задачи из СдамГИА.

    `subject` — ключ из `bot.catalog.SUBJECTS` (math/russian/...), а не код
    sdamgia (math/rus/...). Уникальность по паре `(subject, sdamgia_id)`,
    потому что один id может встретиться в разных предметах.
    """

    __tablename__ = "problems"
    __table_args__ = (
        UniqueConstraint("subject", "sdamgia_id", name="uq_problems_subject_sdamgia_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    sdamgia_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)

    topic_number: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    topic_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    category_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    condition_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition_images: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    solution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_images: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    analogs: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
