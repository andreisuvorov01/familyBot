from pydantic import BaseModel
from datetime import datetime
from .task import TaskVisibility

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
    visibility: TaskVisibility
    created_at: datetime
    subtasks: list[SubtaskRead] = [] # <-- Теперь задача содержит список подзадач

    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    visibility: TaskVisibility = TaskVisibility.COMMON

class TaskUpdate(BaseModel):
    status: str | None = None
    title: str | None = None
