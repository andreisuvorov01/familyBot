from datetime import datetime
from typing import List, Optional

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.models.Task import Subtask, Task, TaskCompletion, TaskVisibility
from app.core.models.user import User


def visible_to(user: User):
    """Условие видимости: общие задачи семьи + личные задачи самого пользователя."""
    return or_(Task.visibility == TaskVisibility.COMMON, Task.owner_id == user.id)


class TaskRepository:
    """Доступ к задачам. Методы делают flush, а commit — вызывающий код (TaskService),
    чтобы изменение задачи и запись в очередь синхронизации шли одной транзакцией."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_family_tasks(self, user: User) -> List[Task]:
        """Получить задачи семьи, видимые пользователю"""
        stmt = (
            select(Task)
            .where(Task.family_id == user.family_id, visible_to(user))
            .options(selectinload(Task.subtasks))
            .order_by(Task.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_task_by_id(self, task_id: int) -> Optional[Task]:
        stmt = select(Task).where(Task.id == task_id).options(selectinload(Task.subtasks))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_visible_task_by_id(self, task_id: int, user: User) -> Optional[Task]:
        stmt = (
            select(Task)
            .where(Task.id == task_id, Task.family_id == user.family_id, visible_to(user))
            .options(selectinload(Task.subtasks))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, task: Task) -> Task:
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task, attribute_names=["subtasks"])
        return task

    async def delete(self, task: Task) -> None:
        await self.session.delete(task)
        await self.session.flush()

    async def get_tasks_by_owner(self, owner_id: int) -> List[Task]:
        result = await self.session.execute(select(Task).where(Task.owner_id == owner_id))
        return list(result.scalars().all())

    async def delete_tasks_by_owner(self, owner_id: int) -> int:
        result = await self.session.execute(delete(Task).where(Task.owner_id == owner_id))
        await self.session.flush()
        return result.rowcount or 0

    async def get_pending_tasks_with_deadlines(self, target_time: datetime) -> List[Task]:
        """Получить задачи с дедлайнами для уведомлений"""
        stmt = select(Task).where(
            Task.status == "pending",
            Task.deadline.is_not(None),
            Task.deadline <= target_time,
            Task.reminder_sent.is_(False),
        ).options(selectinload(Task.subtasks))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_visible_tasks(self, user: User) -> List[Task]:
        """Незавершённые задачи, видимые пользователю (без чужих личных)."""
        stmt = select(Task).where(
            Task.family_id == user.family_id,
            Task.status == "pending",
            visible_to(user),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_completion(self, task: Task, user: User, at: datetime) -> None:
        self.session.add(TaskCompletion(task_id=task.id, user_id=user.id, family_id=task.family_id, completed_at=at))

    async def get_completions(self, family_id: str, since: datetime) -> List[TaskCompletion]:
        stmt = (
            select(TaskCompletion)
            .where(TaskCompletion.family_id == family_id, TaskCompletion.completed_at >= since)
            .order_by(TaskCompletion.completed_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_subtask(self, task_id: int, title: str) -> Subtask:
        subtask = Subtask(title=title, task_id=task_id)
        self.session.add(subtask)
        await self.session.flush()
        await self.session.refresh(subtask)
        return subtask

    async def get_visible_subtask(self, subtask_id: int, user: User) -> Optional[Subtask]:
        stmt = (
            select(Subtask)
            .join(Task, Task.id == Subtask.task_id)
            .where(Subtask.id == subtask_id, Task.family_id == user.family_id, visible_to(user))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_subtask(self, subtask: Subtask) -> None:
        await self.session.delete(subtask)
        await self.session.flush()
