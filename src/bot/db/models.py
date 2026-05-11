from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # auth: email опционален (Telegram-only вход), но email+password_hash идут парой
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    # telegram-связка: можно входить и без неё
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, index=True, nullable=True
    )
    first_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    username: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # онбординг (наследие из бота — оставляем тут, /me/profile его и редактирует)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subjects: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    weekly_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # пользовательские настройки (notifications, theme и пр.) — свободный JSON
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RefreshToken(Base):
    """Хранится hash (sha256) от refresh-токена — сам токен видит только клиент."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TelegramLinkCode(Base):
    """Одноразовый код для линковки Telegram-аккаунта к существующему API-юзеру."""

    __tablename__ = "telegram_link_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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


class Bookmark(Base):
    __tablename__ = "bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "problem_id", name="uq_bookmarks_user_problem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProblemReport(Base):
    __tablename__ = "problem_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(32), nullable=False)  # wrong_answer/typo/broken_image/other
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)  # open/reviewed/closed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Variant(Base):
    """Сборка задач в один «вариант ЕГЭ». В фазе 1 создаются автоматически
    при /attempts/start с problem_ids (kind=synthetic) или вручную позже.
    """

    __tablename__ = "variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # упорядоченный список problem.id; порядок = позиция в варианте
    problem_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="synthetic", nullable=False)
    # synthetic = создан inline под attempt, assembled = ручная сборка, generated = по blueprint
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="in_progress", nullable=False)
    # in_progress / paused / submitted / abandoned
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    primary_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    test_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "problem_id", name="uq_attempt_answers_attempt_problem"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    primary_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # для части 2: критерии (jsonb), {criterion_id: points}
    criteria_scores: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Blueprint(Base):
    """Структура варианта ЕГЭ для предмета: позиции, тема каждой позиции, макс балл,
    тип ответа (short/extended/essay). Источник — кодификатор ФИПИ-2025.
    """

    __tablename__ = "blueprints"
    __table_args__ = (
        UniqueConstraint("subject", "version", name="uq_blueprints_subject_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(16), default="2025", nullable=False)
    # [{position, topic_number, part, max_score, answer_type}]
    slots: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    total_positions: Mapped[int] = mapped_column(Integer, nullable=False)
    max_primary_score: Mapped[int] = mapped_column(Integer, nullable=False)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ScoringRule(Base):
    """Шкала перевода первичного балла в тестовый + минимальный порог."""

    __tablename__ = "scoring_rules"
    __table_args__ = (
        UniqueConstraint("subject", "version", name="uq_scoring_rules_subject_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(16), default="2025", nullable=False)
    # {primary_score: test_score}; ключи — строки в JSON
    primary_to_test: Mapped[dict] = mapped_column(JSONB, nullable=False)
    min_test_score_pass: Mapped[int] = mapped_column(Integer, nullable=False)
    min_test_score_university: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# индексы под частые запросы
Index("ix_attempts_user_status", Attempt.user_id, Attempt.status)
Index("ix_bookmarks_user_created", Bookmark.user_id, Bookmark.created_at.desc())
