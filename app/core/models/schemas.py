from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List
from enum import Enum
from .Task import TaskVisibility
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
    tg_id: int
    username: Optional[str] = None
    role: Optional[UserRole] = None
    family_id: str
    notifications_enabled: bool
    task_creation_mode: TaskCreationMode

    model_config = {"from_attributes": True}


class UserSettingsUpdate(BaseModel):
    notifications_enabled: Optional[bool] = None
    task_creation_mode: Optional[TaskCreationMode] = None
    role: Optional[UserRole] = None

    model_config = {"extra": "forbid"}


import pytz

class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    repeat_rule: Optional[str] = None
    visibility: TaskVisibility
    deadline: Optional[datetime] = None
    created_at: datetime
    subtasks: List[SubtaskRead] = Field(default_factory=list)

    @field_validator('deadline', 'created_at', mode='before')
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
    deadline: Optional[datetime] = None
    repeat_rule: Optional[RepeatRuleEnum] = None

    @field_validator('deadline')
    @classmethod
    def validate_deadline(cls, v):
        # Удаляем проверку на прошлое время, так как она может вызывать ошибки
        # из-за разницы в миллисекундах или часовых поясах
        return v

    model_config = {"extra": "forbid"}


class TaskUpdate(BaseModel):
    status: Optional[TaskStatusEnum] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1024)
    deadline: Optional[datetime] = None
    visibility: Optional[TaskVisibilityEnum] = None
    repeat_rule: Optional[RepeatRuleEnum] = None

    @field_validator('deadline')
    @classmethod
    def validate_deadline(cls, v):
        return v

    model_config = {"extra": "forbid"}
