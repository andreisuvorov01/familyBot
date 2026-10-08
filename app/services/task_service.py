"""Бизнес-логика задач — общая для Mini App (API) и бота.

Любое изменение задачи проходит через TaskService: так одинаково работают повторы,
история выполнений, уведомления партнёру и очередь синхронизации с Google Calendar.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.Task import Subtask, Task, TaskPriority, TaskVisibility
from app.core.models.user import User, UserRole
from app.core.repositories.task_repository import TaskRepository
from app.core.repositories.user_repository import UserRepository
from app.core.timeutils import format_local, next_occurrence, to_local, utcnow
from app.services import calendar_sync, gamification
from app.services.notifications import display_name, h, notify_users

UPDATABLE_FIELDS = {"title", "description", "deadline", "visibility", "priority", "repeat_rule", "status"}


class TaskError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TaskNotFound(TaskError):
    def __init__(self, what: str = "Task"):
        super().__init__(f"{what} not found", 404)


@dataclass
class StatusChange:
    """Что произошло при смене статуса — для текста уведомлений."""

    kind: str  # "completed" | "rescheduled" | "reopened" | "cancelled" | "none"


def private_visibility_for(user: User) -> TaskVisibility:
    # Значение HUSBAND/WIFE сохраняется для совместимости; доступ определяет owner_id
    return TaskVisibility.WIFE if user.role == UserRole.WIFE else TaskVisibility.HUSBAND


class TaskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.tasks = TaskRepository(session)
        self.users = UserRepository(session)

    # --- Чтение ---

    async def list_tasks(self, user: User) -> list[Task]:
        return await self.tasks.get_family_tasks(user)

    async def get_task(self, user: User, task_id: int) -> Task:
        task = await self.tasks.get_visible_task_by_id(task_id, user)
        if not task:
            raise TaskNotFound()
        return task

    # --- Создание ---

    async def create_task(
        self,
        user: User,
        *,
        title: str,
        description: Optional[str] = None,
        private: bool = False,
        priority: Optional[TaskPriority | str] = None,
        deadline: Optional[datetime] = None,
        repeat_rule: Optional[str] = None,
        notify: bool = True,
    ) -> Task:
        task = Task(
            title=title.strip(),
            description=(description or "").strip() or None,
            visibility=private_visibility_for(user) if private else TaskVisibility.COMMON,
            priority=TaskPriority(priority) if priority else None,
            deadline=deadline,
            repeat_rule=repeat_rule,
            owner_id=user.id,
            family_id=user.family_id,
            status="pending",
            reminder_sent=False,
        )
        await self.tasks.add(task)
        await calendar_sync.enqueue_upsert(self.session, task)
        await self.session.commit()

        if notify and not task.is_private:
            await self._notify_partners(user, task, lambda r: self._created_text(user, task, r))
        return task

    # --- Изменение ---

    async def update_task(self, user: User, task_id: int, changes: dict[str, Any]) -> Task:
        """changes — только переданные поля (visibility: "private" | "common")."""
        task = await self.get_task(user, task_id)
        unknown = set(changes) - UPDATABLE_FIELDS
        if unknown:
            raise TaskError(f"Unknown fields: {', '.join(sorted(unknown))}")

        if "title" in changes:
            title = (changes["title"] or "").strip()
            if not title:
                raise TaskError("Title must not be empty")
            task.title = title
        if "description" in changes:
            task.description = (changes["description"] or "").strip() or None
        if "priority" in changes:
            task.priority = TaskPriority(changes["priority"]) if changes["priority"] else None
        if "repeat_rule" in changes:
            task.repeat_rule = changes["repeat_rule"] or None
        if "deadline" in changes and changes["deadline"] != task.deadline:
            task.deadline = changes["deadline"]
            task.reminder_sent = False
        if "visibility" in changes and changes["visibility"]:
            self._apply_visibility(user, task, changes["visibility"])

        change = StatusChange("none")
        if changes.get("status"):
            change = await self._apply_status(user, task, changes["status"])

        task.updated_at = utcnow()
        await calendar_sync.enqueue_upsert(self.session, task)
        await self.session.commit()
        await self._notify_status_change(user, task, change)
        return task

    async def complete_task(self, user: User, task_id: int) -> tuple[Task, StatusChange]:
        """Выполнение из бота (кнопка в уведомлении)."""
        task = await self.get_task(user, task_id)
        if task.status == "done":
            return task, StatusChange("none")
        change = await self._apply_status(user, task, "done")
        task.updated_at = utcnow()
        await calendar_sync.enqueue_upsert(self.session, task)
        await self.session.commit()
        await self._notify_status_change(user, task, change)
        return task, change

    def _apply_visibility(self, user: User, task: Task, visibility: str) -> None:
        if visibility == "common":
            task.visibility = TaskVisibility.COMMON
        elif visibility == "private":
            if task.owner_id != user.id:
                raise TaskError("Сделать задачу личной может только её автор", 403)
            if not task.is_private:
                task.visibility = private_visibility_for(user)
        else:
            raise TaskError(f"Unknown visibility: {visibility}")

    async def _apply_status(self, user: User, task: Task, status: str) -> StatusChange:
        now = utcnow()
        if status == "done":
            if task.status == "done":
                return StatusChange("none")
            await self.tasks.add_completion(task, user, now)
            if task.repeat_rule:
                # Повторяющаяся задача: остаётся в работе, дедлайн переносится на следующий повтор
                if task.deadline:
                    task.deadline = next_occurrence(task.deadline, task.repeat_rule, user.timezone, now)
                task.status = "pending"
                task.reminder_sent = False
                for subtask in task.subtasks:
                    subtask.is_done = False
                return StatusChange("rescheduled")
            task.status = "done"
            task.completed_at = now
            task.completed_by_id = user.id
            return StatusChange("completed")

        if status == "pending":
            was_done = task.status != "pending"
            task.status = "pending"
            task.completed_at = None
            task.completed_by_id = None
            if task.deadline and task.deadline > now:
                task.reminder_sent = False
            return StatusChange("reopened" if was_done else "none")

        if status == "cancelled":
            task.status = "cancelled"
            return StatusChange("cancelled")

        raise TaskError(f"Unknown status: {status}")

    # --- Удаление ---

    async def delete_task(self, user: User, task_id: int) -> Task:
        task = await self.get_task(user, task_id)
        await calendar_sync.enqueue_delete(self.session, task)
        await self.tasks.delete(task)
        await self.session.commit()
        return task

    async def delete_user(self, user: User) -> None:
        """Удалить профиль и задачи пользователя (события в календарях партнёров тоже)."""
        for task in await self.tasks.get_tasks_by_owner(user.id):
            await calendar_sync.enqueue_delete(self.session, task)
        await self.tasks.delete_tasks_by_owner(user.id)
        await self.session.delete(user)
        await self.session.commit()

    # --- Подзадачи ---

    async def add_subtask(self, user: User, task_id: int, title: str) -> Subtask:
        task = await self.get_task(user, task_id)
        subtask = await self.tasks.add_subtask(task.id, title.strip())
        task.updated_at = utcnow()
        await calendar_sync.enqueue_upsert(self.session, task)
        await self.session.commit()
        return subtask

    async def set_subtask_done(self, user: User, subtask_id: int, is_done: bool) -> Subtask:
        subtask = await self._get_subtask(user, subtask_id)
        subtask.is_done = is_done
        await self._touch_parent(subtask.task_id)
        await self.session.commit()
        return subtask

    async def delete_subtask(self, user: User, subtask_id: int) -> None:
        subtask = await self._get_subtask(user, subtask_id)
        task_id = subtask.task_id
        await self.tasks.delete_subtask(subtask)
        await self._touch_parent(task_id)
        await self.session.commit()

    async def _get_subtask(self, user: User, subtask_id: int) -> Subtask:
        subtask = await self.tasks.get_visible_subtask(subtask_id, user)
        if not subtask:
            raise TaskNotFound("Subtask")
        return subtask

    async def _touch_parent(self, task_id: int) -> None:
        task = await self.tasks.get_task_by_id(task_id)
        if task:
            task.updated_at = utcnow()
            await calendar_sync.enqueue_upsert(self.session, task)

    # --- Статистика ---

    async def get_stats(self, user: User) -> dict[str, Any]:
        tasks = await self.tasks.get_family_tasks(user)
        now = utcnow()
        pending = [t for t in tasks if t.status == "pending"]
        completions = await self.tasks.get_completions(user.family_id or "", datetime(1970, 1, 1))

        members = [user] + await self.users.get_partners(user)
        week_ago, month_ago = now - timedelta(days=7), now - timedelta(days=30)
        week_by_user = Counter(c.user_id for c in completions if c.completed_at >= week_ago)
        month_by_user = Counter(c.user_id for c in completions if c.completed_at >= month_ago)
        total_by_user = Counter(c.user_id for c in completions)

        # Серия: сколько дней подряд (по поясу пользователя) семья что-то выполняла
        done_days = {to_local(c.completed_at, user.timezone).date() for c in completions}
        today = to_local(now, user.timezone).date()
        day = today if today in done_days else today - timedelta(days=1)
        streak = 0
        while day in done_days:
            streak += 1
            day -= timedelta(days=1)

        # Выполнения по дням за последнюю неделю (для мини-графика)
        per_day = Counter(to_local(c.completed_at, user.timezone).date() for c in completions)
        week = [
            {"date": (today - timedelta(days=i)).isoformat(), "count": per_day.get(today - timedelta(days=i), 0)}
            for i in range(6, -1, -1)
        ]

        return {
            "total": len(tasks),
            "pending": len(pending),
            "done": len([t for t in tasks if t.status == "done"]),
            "overdue": len([t for t in pending if t.deadline and t.deadline < now]),
            "done_this_week": sum(week_by_user.values()),
            "streak_days": streak,
            "week": week,
            "members": [
                {
                    "name": "Вы" if m.id == user.id else display_name(m),
                    "is_me": m.id == user.id,
                    "done_week": week_by_user.get(m.id, 0),
                    "done_month": month_by_user.get(m.id, 0),
                    **gamification.progress(total_by_user.get(m.id, 0), streak),
                }
                for m in members
            ],
        }

    # --- Уведомления ---

    async def _notify_partners(self, actor: User, task: Task, build_text) -> None:
        partners = await self.users.get_partners(actor)
        await notify_users(partners, build_text, task_id=task.id)

    async def _notify_status_change(self, actor: User, task: Task, change: StatusChange) -> None:
        if task.is_private or change.kind not in ("completed", "rescheduled"):
            return

        def text(recipient: User) -> str:
            if change.kind == "rescheduled":
                msg = f"🔄 <b>Задача выполнена и перенесена!</b>\n{h(task.title)}"
                if task.deadline:
                    msg += f"\n⏰ Следующий раз: {format_local(task.deadline, recipient.timezone)}"
            else:
                msg = f"✅ <b>Задача выполнена!</b>\n<s>{h(task.title)}</s>"
            return msg + f"\n<i>{h(display_name(actor))}</i>"

        await self._notify_partners(actor, task, text)

    @staticmethod
    def _created_text(actor: User, task: Task, recipient: User) -> str:
        text = f"🆕 <b>Новая задача!</b>\n📌 {h(task.title)}"
        if task.deadline:
            text += f"\n⏰ <b>Дедлайн:</b> {format_local(task.deadline, recipient.timezone)}"
        if task.priority == TaskPriority.HIGH:
            text += "\n🔥 Высокий приоритет"
        return text + f"\n<i>Добавил(а): {h(display_name(actor))}</i>"
