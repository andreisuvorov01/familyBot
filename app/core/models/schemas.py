from pydantic import BaseModel, Field, validator, ConfigDict
from datetime import datetime
from typing import Optional, List
from enum import Enum
from .Task import TaskVisibility


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

    model_config = ConfigDict(strict=True)


class SubtaskRead(SubtaskBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class SubtaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)

    model_config = ConfigDict(strict=True)


class TaskRead(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    repeat_rule: str | None = None
    visibility: TaskVisibility
    deadline: datetime | None
    created_at: datetime
    subtasks: list[SubtaskRead] = []

    model_config = ConfigDict(from_attributes=True)


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1024)
    visibility: TaskVisibilityEnum = TaskVisibilityEnum.COMMON
    deadline: datetime | None = None
    repeat_rule: RepeatRuleEnum | None = None

    @validator('deadline')
    def validate_deadline(cls, v):
        if v and v < datetime.utcnow():
            raise ValueError('Deadline cannot be in the past')
        return v

    model_config = ConfigDict(strict=True)


class TaskUpdate(BaseModel):
    status: TaskStatusEnum | None = None
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1024)
    deadline: datetime | None = None
    visibility: TaskVisibilityEnum | None = None
    repeat_rule: RepeatRuleEnum | None = None

    @validator('deadline')
    def validate_deadline(cls, v):
        if v and v < datetime.utcnow():
            raise ValueError('Deadline cannot be in the past')
        return v

    model_config = ConfigDict(strict=True)
