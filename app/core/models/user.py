import enum
from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class UserRole(enum.Enum):
    HUSBAND = "husband"
    WIFE = "wife"


class TaskCreationMode(enum.Enum):
    COMMAND = "command"
    MESSAGE = "message"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=True)
    family_id: Mapped[str | None] = mapped_column(String(10), index=True)  # Код для связки пары
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
    morning_summary_enabled: Mapped[bool] = mapped_column(default=True)
    task_creation_mode: Mapped[TaskCreationMode] = mapped_column(Enum(TaskCreationMode), default=TaskCreationMode.COMMAND)
