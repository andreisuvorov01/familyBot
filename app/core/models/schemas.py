from datetime import datetime
from enum import Enum
from typing import List, Optional

import pytz
from pydantic import BaseModel, Field, field_validator

from .Task import TaskPriority, TaskVisibility
from .user import TaskCreationMode, UserRole


class TaskVisibilityEnum(str, Enum):
    PRIVATE = "private"
    COMMON = "common"


class RepeatRuleEnum(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriorityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SubtaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    is_done: bool = False

    model_config = {"extra": "forbid"}


class SubtaskRead(SubtaskBase):
    id: int

    model_config = {"from_attributes": True}


class SubtaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)

    model_config = {"extra": "forbid"}


class SubtaskUpdate(BaseModel):
    is_done: bool

    model_config = {"extra": "forbid"}


class UserSettingsRead(BaseModel):
    id: int
    tg_id: int
    username: Optional[str] = None
    role: Optional[UserRole] = None
    family_id: str
    notifications_enabled: bool
    morning_summary_enabled: bool
    task_creation_mode: TaskCreationMode
    timezone: str

    model_config = {"from_attributes": True}


class UserSettingsUpdate(BaseModel):
    notifications_enabled: Optional[bool] = None
    morning_summary_enabled: Optional[bool] = None
    task_creation_mode: Optional[TaskCreationMode] = None
    role: Optional[UserRole] = None
    timezone: Optional[str] = Field(None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v):
        if v is not None and v not in pytz.all_timezones_set:
            raise ValueError("Unknown timezone")
        return v

    model_config = {"extra": "forbid"}


def _to_naive_utc(v):
    """Дедлайны из клиента приходят с поясом; в БД храним наивный UTC."""
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.astimezone(pytz.UTC).replace(tzinfo=None)
    return v


class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    repeat_rule: Optional[str] = None
    visibility: TaskVisibility
    priority: Optional[TaskPriority] = None
    deadline: Optional[datetime] = None
    owner_id: int
    completed_at: Optional[datetime] = None
    completed_by_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    subtasks: List[SubtaskRead] = Field(default_factory=list)

    @field_validator("deadline", "created_at", "updated_at", "completed_at", mode="before")
    @classmethod
    def ensure_utc(cls, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return pytz.UTC.localize(v)
        return v

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1024)
    visibility: TaskVisibilityEnum = TaskVisibilityEnum.COMMON
    priority: Optional[TaskPriorityEnum] = None
    deadline: Optional[datetime] = None
    repeat_rule: Optional[RepeatRuleEnum] = None

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v):
        return _to_naive_utc(v)

    model_config = {"extra": "forbid"}


class TaskUpdate(BaseModel):
    status: Optional[TaskStatusEnum] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1024)
    deadline: Optional[datetime] = None
    visibility: Optional[TaskVisibilityEnum] = None
    priority: Optional[TaskPriorityEnum] = None
    repeat_rule: Optional[RepeatRuleEnum] = None

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v):
        return _to_naive_utc(v)

    model_config = {"extra": "forbid"}


class Badge(BaseModel):
    id: str
    icon: str
    title: str
    earned: bool


class TaskStatsMember(BaseModel):
    name: str
    is_me: bool
    done_week: int
    done_month: int
    xp: int
    level: int
    level_xp: int
    level_xp_needed: int
    badges: List[Badge]


class TaskStatsDay(BaseModel):
    date: str
    count: int


class TaskStats(BaseModel):
    total: int
    pending: int
    done: int
    overdue: int
    done_this_week: int
    streak_days: int
    week: List[TaskStatsDay]
    members: List[TaskStatsMember]


class GoogleStatus(BaseModel):
    available: bool
    connected: bool
    enabled: bool = False
    email: Optional[str] = None
    last_error: Optional[str] = None
    last_synced_at: Optional[datetime] = None
