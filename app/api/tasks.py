from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_async_session
from app.core.logging_config import log_with_context
from app.core.models.schemas import (
    SubtaskCreate,
    SubtaskRead,
    SubtaskUpdate,
    TaskCreate,
    TaskRead,
    TaskStats,
    TaskUpdate,
    UserSettingsRead,
    UserSettingsUpdate,
)
from app.core.models.user import User
from app.core.repositories.user_repository import UserRepository
from app.services.task_service import TaskError, TaskService

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def get_service(session: AsyncSession = Depends(get_async_session)) -> TaskService:
    return TaskService(session)


def _http_error(e: TaskError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)


# --- TASKS ---


@router.get("/", response_model=list[TaskRead])
async def get_tasks(user: User = Depends(get_current_user), service: TaskService = Depends(get_service)):
    """Получить задачи семьи, видимые пользователю"""
    return await service.list_tasks(user)


@router.post("/", response_model=TaskRead)
async def create_task(
    task_in: TaskCreate,
    user: User = Depends(get_current_user),
    service: TaskService = Depends(get_service),
):
    """Создать новую задачу"""
    task = await service.create_task(
        user,
        title=task_in.title,
        description=task_in.description,
        private=task_in.visibility.value == "private",
        priority=task_in.priority.value if task_in.priority else None,
        deadline=task_in.deadline,
        repeat_rule=task_in.repeat_rule.value if task_in.repeat_rule else None,
    )
    log_with_context("INFO", "Task created", user_id=user.id, task_id=task.id)
    return task


@router.get("/stats", response_model=TaskStats)
async def get_stats(user: User = Depends(get_current_user), service: TaskService = Depends(get_service)):
    """Статистика семьи для Mini App"""
    return await service.get_stats(user)


# --- PROFILE / MINI APP SETTINGS ---


@router.get("/profile", response_model=UserSettingsRead)
async def get_profile(user: User = Depends(get_current_user)):
    """Получить настройки текущего пользователя для Mini App."""
    return user


@router.patch("/profile", response_model=UserSettingsRead)
async def update_profile(
    updates: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Обновить настройки текущего пользователя из Mini App."""
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        return user

    await UserRepository(session).update_settings(user.tg_id, **update_data)
    for key, value in update_data.items():
        setattr(user, key, value)

    log_with_context("INFO", "User profile updated", user_id=user.id, fields=list(update_data.keys()))
    return user


@router.delete("/profile")
async def delete_profile(user: User = Depends(get_current_user), service: TaskService = Depends(get_service)):
    """Удалить профиль текущего пользователя и его задачи."""
    await service.delete_user(user)
    log_with_context("INFO", "User profile deleted from Mini App", user_id=user.id)
    return {"ok": True}


# --- SINGLE TASK ---


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: int, user: User = Depends(get_current_user), service: TaskService = Depends(get_service)):
    try:
        return await service.get_task(user, task_id)
    except TaskError as e:
        raise _http_error(e)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    updates: TaskUpdate,
    user: User = Depends(get_current_user),
    service: TaskService = Depends(get_service),
):
    """Обновить задачу (передаются только изменённые поля)"""
    changes = {}
    for field in updates.model_fields_set:
        value = getattr(updates, field)
        changes[field] = value.value if hasattr(value, "value") else value
    try:
        task = await service.update_task(user, task_id, changes)
    except TaskError as e:
        raise _http_error(e)
    log_with_context("INFO", "Task updated", user_id=user.id, task_id=task_id, fields=sorted(changes))
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: int, user: User = Depends(get_current_user), service: TaskService = Depends(get_service)
):
    """Удалить задачу"""
    try:
        await service.delete_task(user, task_id)
    except TaskError as e:
        raise _http_error(e)
    log_with_context("INFO", "Task deleted", user_id=user.id, task_id=task_id)
    return {"ok": True}


# --- SUBTASKS ---


@router.post("/{task_id}/subtasks", response_model=SubtaskRead)
async def add_subtask(
    task_id: int,
    sub_in: SubtaskCreate,
    user: User = Depends(get_current_user),
    service: TaskService = Depends(get_service),
):
    """Добавить подзадачу"""
    try:
        return await service.add_subtask(user, task_id, sub_in.title)
    except TaskError as e:
        raise _http_error(e)


@router.patch("/subtasks/{sub_id}")
async def toggle_subtask(
    sub_id: int,
    updates: SubtaskUpdate,
    user: User = Depends(get_current_user),
    service: TaskService = Depends(get_service),
):
    """Переключить статус подзадачи"""
    try:
        await service.set_subtask_done(user, sub_id, updates.is_done)
    except TaskError as e:
        raise _http_error(e)
    return {"ok": True}


@router.delete("/subtasks/{sub_id}")
async def delete_subtask(
    sub_id: int, user: User = Depends(get_current_user), service: TaskService = Depends(get_service)
):
    """Удалить подзадачу."""
    try:
        await service.delete_subtask(user, sub_id)
    except TaskError as e:
        raise _http_error(e)
    return {"ok": True}
