import enum
from datetime import datetime
from sqlalchemy import String, Enum, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class TaskVisibility(enum.Enum):
    HUSBAND = "husband"
    WIFE = "wife"
    COMMON = "common"


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

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    family_id: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связь с подзадачами (Eager loading)
    subtasks: Mapped[list["Subtask"]] = relationship(
        "Subtask",
        backref="task",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
