from pydantic import BaseModel
from datetime import datetime
from .Task import TaskVisibility
from typing import Optional

# --- Subtasks ---
class SubtaskBase(BaseModel):
    title: str
    is_done: bool = False

class SubtaskRead(SubtaskBase):
    id: int
    class Config:
        from_attributes = True

class SubtaskCreate(BaseModel):
    title: str

# --- Tasks ---
class TaskRead(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    repeat_rule: str | None = None
    visibility: TaskVisibility
    deadline: datetime | None # <-- Новое поле
    created_at: datetime
    subtasks: list[SubtaskRead] = []

    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    visibility: str = "common"
    deadline: datetime | None = None
    repeat_rule: str | None = None

class TaskUpdate(BaseModel):
    # Делаем всё Optional и str, чтобы не было конфликтов типов
    status: str | None = None
    title: str | None = None
    description: str | None = None
    deadline: datetime | None = None
    visibility: str | None = None
    repeat_rule: str | None = None
