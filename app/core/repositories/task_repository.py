from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, delete, update, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.models.Task import Task, TaskVisibility, Subtask
from app.core.models.user import UserRole


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_family_tasks(self, family_id: str, user_role: UserRole) -> List[Task]:
        """Получить задачи семьи с учетом видимости"""
        visibilities = [TaskVisibility.COMMON]
        if user_role == UserRole.HUSBAND:
            visibilities.append(TaskVisibility.HUSBAND)
        else:
            visibilities.append(TaskVisibility.WIFE)

        stmt = (
            select(Task)
            .where(
                Task.family_id == family_id,
                Task.visibility.in_(visibilities)
            )
            .options(selectinload(Task.subtasks))
            .order_by(Task.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_task_by_id(self, task_id: int, family_id: str) -> Optional[Task]:
        stmt = (
            select(Task)
            .where(
                Task.id == task_id,
                Task.family_id == family_id
            )
            .options(selectinload(Task.subtasks))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_task(
        self,
        title: str,
        owner_id: int,
        family_id: str,
        description: Optional[str] = None,
        visibility: TaskVisibility = TaskVisibility.COMMON,
        deadline: Optional[datetime] = None,
        repeat_rule: Optional[str] = None
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            visibility=visibility,
            deadline=deadline,
            repeat_rule=repeat_rule,
            owner_id=owner_id,
            family_id=family_id
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task, attribute_names=["subtasks"])
        return task

    async def update_task(
        self,
        task_id: int,
        family_id: str,
        **updates
    ) -> Optional[Task]:
        task = await self.get_task_by_id(task_id, family_id)
        if not task:
            return None

        for key, value in updates.items():
            if value is not None:
                setattr(task, key, value)

        await self.session.commit()
        return task

    async def delete_task(self, task_id: int, family_id: str) -> bool:
        stmt = delete(Task).where(
            Task.id == task_id,
            Task.family_id == family_id
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_pending_tasks_with_deadlines(
        self,
        target_time: datetime
    ) -> List[Task]:
        """Получить задачи с дедлайнами для уведомлений"""
        stmt = select(Task).where(
            Task.status == "pending",
            Task.deadline != None,
            Task.deadline <= target_time,
            Task.reminder_sent == False
        ).options(selectinload(Task.subtasks))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_pending_tasks_by_family(self, family_id: str) -> List[Task]:
        stmt = select(Task).where(
            Task.family_id == family_id,
            Task.status == "pending"
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add_subtask(self, task_id: int, title: str) -> Subtask:
        subtask = Subtask(title=title, task_id=task_id)
        self.session.add(subtask)
        await self.session.commit()
        await self.session.refresh(subtask)
        return subtask

    async def toggle_subtask(self, subtask_id: int, is_done: bool) -> bool:
        stmt = update(Subtask).where(Subtask.id == subtask_id).values(is_done=is_done)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0