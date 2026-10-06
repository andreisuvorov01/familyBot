from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GoogleAccount(Base):
    """Подключённый Google-аккаунт пользователя (1:1 с User)."""

    __tablename__ = "google_accounts"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255))
    refresh_token_enc: Mapped[str] = mapped_column(Text)
    calendar_id: Mapped[str | None] = mapped_column(String(255))
    sync_token: Mapped[str | None] = mapped_column(String(512))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_error: Mapped[str | None] = mapped_column(String(512))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)


class TaskCalendarEvent(Base):
    """Связь задачи с событием в календаре конкретного пользователя."""

    __tablename__ = "task_calendar_events"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_calendar_events_task_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(255), index=True)
    etag: Mapped[str | None] = mapped_column(String(255))


class CalendarSyncJob(Base):
    """Outbox: изменения задач, которые нужно отправить в Google Calendar.

    Строка пишется в той же транзакции, что и изменение задачи, а разбирает очередь
    планировщик в процессе бота (app/services/calendar_sync.py).
    """

    __tablename__ = "calendar_sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Без FK: задача к моменту обработки может быть уже удалена
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(16))  # "upsert" | "delete"
    # Для delete: [{"user_id": ..., "event_id": ...}] — связи удаляются каскадом вместе с задачей
    payload: Mapped[list | None] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_error: Mapped[str | None] = mapped_column(String(512))
