import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class TaskVisibility(str, enum.Enum):
    # HUSBAND/WIFE исторически означают «личная задача». Кто её видит, определяет
    # owner_id (см. TaskRepository.visible_to), а не роль пользователя.
    HUSBAND = "husband"
    WIFE = "wife"
    COMMON = "common"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Subtask(Base):
    __tablename__ = "subtasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    visibility: Mapped[TaskVisibility] = mapped_column(Enum(TaskVisibility), default=TaskVisibility.COMMON)

    # Все даты хранятся как наивный UTC
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[TaskPriority | None] = mapped_column(Enum(TaskPriority), nullable=True)

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    family_id: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    subtasks: Mapped[list["Subtask"]] = relationship(
        "Subtask", backref="task", lazy="selectin", cascade="all, delete-orphan"
    )
    repeat_rule: Mapped[str | None] = mapped_column(String(20), nullable=True)

    @property
    def is_private(self) -> bool:
        return self.visibility != TaskVisibility.COMMON


class TaskCompletion(Base):
    """История выполнений (в т.ч. повторяющихся задач) — для статистики."""

    __tablename__ = "task_completions"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    family_id: Mapped[str] = mapped_column(String(10), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
