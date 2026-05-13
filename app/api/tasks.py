from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional

from app.core.database import get_async_session
from app.core.models.user import User, UserRole
from app.core.models.Task import TaskVisibility
from app.core.models.schemas import TaskRead, TaskCreate, TaskUpdate, SubtaskCreate, SubtaskRead
from app.api.security import verify_telegram_data
from app.core.security.rate_limiter import check_auth_rate_limit
from app.core.logging_config import log_with_context, log_function_call
from app.core.repositories.user_repository import UserRepository
from app.core.repositories.task_repository import TaskRepository
from app.bot.instance import bot

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# --- Helper: Получение текущего юзера ---
async def get_current_user(
        init_data: str = Header(..., alias="X-TG-Data"),
        session: AsyncSession = Depends(get_async_session)
) -> User:
    try:
        # Rate limiting для аутентификации
        user_data = verify_telegram_data(init_data)
        tg_id = user_data["id"]
        
        if not check_auth_rate_limit(tg_id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many authentication attempts"
            )
        
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(tg_id)
        
        if not user or not user.family_id:
            log_with_context(
                "WARNING",
                "Access denied: user not found or no family",
                user_id=tg_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        log_with_context(
            "INFO",
            "User authenticated successfully",
            user_id=user.id,
            family_id=user.family_id
        )
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        log_with_context(
            "ERROR",
            f"Authentication failed: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


# --- Helper: Отправка уведомления партнеру ---
async def notify_partner(
    session: AsyncSession,
    user: User,
    message: str,
    task_title: Optional[str] = None
):
    try:
        user_repo = UserRepository(session)
        partner = await user_repo.get_partner(user)
        
        if partner:
            await bot.send_message(partner.tg_id, message, parse_mode="HTML")
            log_with_context(
                "INFO",
                "Partner notification sent",
                user_id=user.id,
                partner_id=partner.id,
                task_title=task_title
            )
    except Exception as e:
        log_with_context(
            "ERROR",
            f"Failed to notify partner: {str(e)}",
            user_id=user.id
        )


# --- TASKS ENDPOINTS ---

@router.get("/", response_model=list[TaskRead])
@log_function_call
async def get_tasks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Получить все задачи семьи"""
    task_repo = TaskRepository(session)
    tasks = await task_repo.get_family_tasks(user.family_id, user.role)
    
    log_with_context(
        "INFO",
        f"Retrieved {len(tasks)} tasks",
        user_id=user.id,
        family_id=user.family_id
    )
    return tasks


@router.post("/", response_model=TaskRead)
@log_function_call
async def create_task(
    task_in: TaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Создать новую задачу"""
    # Конвертируем visibility в TaskVisibility
    visibility_map = {
        "private": TaskVisibility.HUSBAND if user.role == UserRole.HUSBAND else TaskVisibility.WIFE,
        "common": TaskVisibility.COMMON
    }
    
    final_visibility = visibility_map.get(task_in.visibility.value, TaskVisibility.COMMON)
    
    task_repo = TaskRepository(session)
    new_task = await task_repo.create_task(
        title=task_in.title,
        description=task_in.description,
        owner_id=user.id,
        family_id=user.family_id,
        visibility=final_visibility,
        deadline=task_in.deadline,
        repeat_rule=task_in.repeat_rule.value if task_in.repeat_rule else None
    )
    
    # Уведомляем только если задача общая
    if final_visibility == TaskVisibility.COMMON:
        text = f"🆕 <b>Новая задача!</b>\n📌 {task_in.title}"

        if task_in.deadline:
            deadline_msk = task_in.deadline + timedelta(hours=3)
            time_str = deadline_msk.strftime('%d.%m в %H:%M')
            text += f"\n⏰ <b>Дедлайн:</b> {time_str}"

        text += f"\n<i>Добавил(а): {user.username or 'Партнер'}</i>"
        await notify_partner(session, user, text, task_in.title)
    
    log_with_context(
        "INFO",
        f"Task created: {task_in.title}",
        user_id=user.id,
        task_id=new_task.id,
        visibility=final_visibility.value
    )
    return new_task


@router.patch("/{task_id}")
@log_function_call
async def update_task(
    task_id: int,
    updates: TaskUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Обновить задачу"""
    task_repo = TaskRepository(session)
    
    # Получаем текущую задачу
    task = await task_repo.get_task_by_id(task_id, user.family_id)
    if not task:
        log_with_context(
            "WARNING",
            f"Task not found: {task_id}",
            user_id=user.id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    old_status = task.status
    
    # Подготавливаем обновления
    update_data = {}
    if updates.title is not None:
        update_data["title"] = updates.title
    if updates.description is not None:
        update_data["description"] = updates.description
    if updates.deadline is not None:
        update_data["deadline"] = updates.deadline
    if updates.repeat_rule is not None:
        update_data["repeat_rule"] = updates.repeat_rule.value
    
    # Обработка visibility
    if updates.visibility is not None:
        visibility_map = {
            "private": TaskVisibility.HUSBAND if user.role == UserRole.HUSBAND else TaskVisibility.WIFE,
            "common": TaskVisibility.COMMON
        }
        update_data["visibility"] = visibility_map.get(updates.visibility.value, TaskVisibility.COMMON)
    
    # Обработка статуса и повторяющихся задач
    if updates.status is not None:
        if updates.status.value == "done" and task.repeat_rule:
            # Для повторяющихся задач не меняем статус, а переносим дедлайн
            update_data["status"] = "pending"
            update_data["reminder_sent"] = False
            
            if task.deadline:
                delta_map = {
                    "daily": timedelta(days=1),
                    "weekly": timedelta(weeks=1),
                    "monthly": timedelta(days=30)
                }
                delta = delta_map.get(task.repeat_rule, timedelta(days=1))
                update_data["deadline"] = task.deadline + delta
                
                # Сбрасываем подзадачи
                for subtask in task.subtasks:
                    subtask.is_done = False
        else:
            update_data["status"] = updates.status.value
    
    # Применяем обновления
    updated_task = await task_repo.update_task(task_id, user.family_id, **update_data)
    
    if not updated_task:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task"
        )
    
    # Уведомление о завершении общей задачи
    if updates.status and updates.status.value == "done" and task.visibility == TaskVisibility.COMMON:
        if task.repeat_rule:
            text = f"🔄 <b>Задача выполнена и перенесена!</b>\n{task.title}"
        else:
            text = f"✅ <b>Задача выполнена!</b>\n<s>{task.title}</s>"
        await notify_partner(session, user, text, task.title)
    
    log_with_context(
        "INFO",
        f"Task updated: {task_id}, status: {old_status} -> {updated_task.status}",
        user_id=user.id,
        task_id=task_id
    )
    return {"ok": True}


@router.delete("/{task_id}")
@log_function_call
async def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Удалить задачу"""
    task_repo = TaskRepository(session)
    
    # Получаем задачу для логирования
    task = await task_repo.get_task_by_id(task_id, user.family_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    success = await task_repo.delete_task(task_id, user.family_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete task"
        )
    
    log_with_context(
        "INFO",
        f"Task deleted: {task.title}",
        user_id=user.id,
        task_id=task_id
    )
    return {"ok": True}


# --- SUBTASKS ---

@router.post("/{task_id}/subtasks", response_model=SubtaskRead)
@log_function_call
async def add_subtask(
    task_id: int,
    sub_in: SubtaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Добавить подзадачу"""
    task_repo = TaskRepository(session)
    
    # Проверяем существование задачи
    task = await task_repo.get_task_by_id(task_id, user.family_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    subtask = await task_repo.add_subtask(task_id, sub_in.title)
    
    log_with_context(
        "INFO",
        f"Subtask added to task {task_id}: {sub_in.title}",
        user_id=user.id,
        task_id=task_id
    )
    return subtask


@router.patch("/subtasks/{sub_id}")
@log_function_call
async def toggle_subtask(
    sub_id: int,
    is_done: bool,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Переключить статус подзадачи"""
    task_repo = TaskRepository(session)
    
    success = await task_repo.toggle_subtask(sub_id, is_done)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subtask not found"
        )
    
    log_with_context(
        "INFO",
        f"Subtask {sub_id} toggled to {is_done}",
        user_id=user.id
    )
    return {"ok": True}
