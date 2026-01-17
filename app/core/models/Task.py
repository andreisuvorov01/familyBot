import enum
from datetime import datetime
from sqlalchemy import String, Enum, ForeignKey, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class TaskVisibility(enum.Enum):
    HUSBAND = "husband"
    WIFE = "wife"
    COMMON = "common"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    visibility: Mapped[TaskVisibility] = mapped_column(Enum(TaskVisibility), default=TaskVisibility.COMMON)

    # Внешние ключи
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    family_id: Mapped[str] = mapped_column(String(10), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
