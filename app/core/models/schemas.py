from pydantic import BaseModel
from datetime import datetime
from .Task import TaskVisibility

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    visibility: TaskVisibility = TaskVisibility.COMMON

class TaskRead(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    visibility: TaskVisibility
    created_at: datetime

    class Config:
        from_attributes = True
