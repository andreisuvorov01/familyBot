from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.core.database import get_async_session
from app.core.models.user import User
from app.core.models.Task import Task, TaskVisibility, Subtask
from app.core.models.schemas import TaskRead, TaskCreate, TaskUpdate, SubtaskCreate, SubtaskRead
from app.api.security import verify_telegram_data
from app.bot.instance import bot

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# --- Helper: Получение текущего юзера ---
async def get_current_user(
        init_data: str = Header(..., alias="X-TG-Data"),
        session: AsyncSession = Depends(get_async_session)
):
    try:
        user_data = verify_telegram_data(init_data)
        stmt = select(User).where(User.tg_id == user_data["id"])
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user or not user.family_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Auth failed")


# --- Helper: Отправка уведомления партнеру ---
async def notify_partner(session: AsyncSession, user: User, message: str):
    try:
        stmt = select(User).where(
            User.family_id == user.family_id,
            User.id != user.id
        )
        partner = (await session.execute(stmt)).scalar_one_or_none()

        if partner:
            await bot.send_message(partner.tg_id, message, parse_mode="HTML")
    except Exception as e:
        print(f"Failed to notify partner: {e}")


# --- TASKS ENDPOINTS ---

@router.get("/", response_model=list[TaskRead])
async def get_tasks(
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    vis = [TaskVisibility.COMMON]
    if user.role.value == "husband":
        vis.append(TaskVisibility.HUSBAND)
    else:
        vis.append(TaskVisibility.WIFE)

    query = select(Task).where(
        Task.family_id == user.family_id,
        Task.visibility.in_(vis)
    ).options(selectinload(Task.subtasks)).order_by(Task.created_at.desc())

    return (await session.execute(query)).scalars().all()


@router.post("/", response_model=TaskRead)
async def create_task(
        task_in: TaskCreate,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # task_in.visibility теперь строка, сравниваем напрямую
    final_visibility = TaskVisibility.COMMON  # По умолчанию

    if task_in.visibility == "private":
        # Конвертируем строку "private" в правильный Enum в зависимости от роли
        final_visibility = TaskVisibility.HUSBAND if user.role.value == "husband" else TaskVisibility.WIFE
    elif task_in.visibility == "common":
        final_visibility = TaskVisibility.COMMON

    new_task = Task(
        title=task_in.title,
        description=task_in.description,
        visibility=final_visibility,
        deadline=task_in.deadline,
        repeat_rule=task_in.repeat_rule,  # <-- ДОБАВЛЕНО
        owner_id=user.id,
        family_id=user.family_id
    )
    session.add(new_task)
    await session.commit()
    await session.refresh(new_task, attribute_names=["subtasks"])

    # Уведомляем только если задача общая
    if final_visibility == TaskVisibility.COMMON:
        text = f"🆕 <b>Новая задача!</b>\n📌 {task_in.title}"

        # Добавляем дедлайн, если он есть
        if task_in.deadline:
            # Конвертируем UTC в МСК (прибавляем 3 часа для красивого отображения)
            # Если твой часовой пояс другой - поменяй цифру 3 на нужную
            deadline_msk = task_in.deadline + timedelta(hours=3)
            time_str = deadline_msk.strftime('%d.%m в %H:%M')
            text += f"\n⏰ <b>Дедлайн:</b> {time_str}"

        text += f"\n<i>Добавил(а): {user.username or 'Партнер'}</i>"

        await notify_partner(session, user, text)

    return new_task


@router.patch("/{task_id}")
async def update_task(
    task_id: int,
    updates: TaskUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    print(f"🔧 PATCH request for Task {task_id}. Data: {updates.dict(exclude_unset=True)}")

    stmt = select(Task).where(Task.id == task_id, Task.family_id == user.family_id)
    task = (await session.execute(stmt)).scalar_one_or_none()
    if not task:
        print(f"❌ Task {task_id} not found or access denied")
        raise HTTPException(404)

    old_status = task.status

    # Обновление полей
    if updates.status is not None:  # Проверяем именно на None, т.к. пустая строка тоже может быть статусом
        task.status = updates.status
    if updates.title: task.title = updates.title
    if updates.description: task.description = updates.description
    if updates.visibility:
        if updates.visibility == "private":
            task.visibility = TaskVisibility.HUSBAND if user.role.value == "husband" else TaskVisibility.WIFE
        elif updates.visibility == "common":
            task.visibility = TaskVisibility.COMMON
    print(f"🔄 Updating Task {task_id}: Status {old_status} -> {task.status}, Repeat: {task.repeat_rule}")
    # Обновление правила повтора (если прислали None - значит удаляем правило)
    # Используем has_key или проверяем наличие в dict, чтобы отличить отсутствие поля от null
    # Но в Pydantic v2 просто проверяем, было ли поле передано
    if updates.repeat_rule is not None or (
            updates.model_dump(exclude_unset=True).get('repeat_rule') is None and 'repeat_rule' in updates.model_dump(
            exclude_unset=True)):
        task.repeat_rule = updates.repeat_rule

    # Логика дедлайна
    if updates.deadline: task.deadline = updates.deadline

    # ЛОГИКА ЗАВЕРШЕНИЯ ПОВТОРЯЮЩЕЙСЯ ЗАДАЧИ
    if updates.status == "done" and task.repeat_rule:
        task.status = "pending"  # Не закрываем, а оставляем активной
        task.reminder_sent = False  # Сбрасываем напоминание

        # Переносим дату
        if task.deadline:
            if task.repeat_rule == "daily":
                task.deadline += timedelta(days=1)
            elif task.repeat_rule == "weekly":
                task.deadline += timedelta(weeks=1)
            elif task.repeat_rule == "monthly":
                task.deadline += timedelta(days=30)

        # Сбрасываем подзадачи
        for sub in task.subtasks:
            sub.is_done = False

    elif updates.status:
        task.status = updates.status

    await session.commit()

    # Уведомление
    if updates.status == "done" and task.visibility == TaskVisibility.COMMON:
        if task.repeat_rule:
            text = f"🔄 <b>Задача выполнена и перенесена!</b>\n{task.title}"
        else:
            text = f"✅ <b>Задача выполнена!</b>\n<s>{task.title}</s>"
        await notify_partner(session, user, text)

    return {"ok": True}


@router.delete("/{task_id}")
async def delete_task(
        task_id: int,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    stmt = delete(Task).where(Task.id == task_id, Task.family_id == user.family_id)
    await session.execute(stmt)
    await session.commit()
    return {"ok": True}


# --- SUBTASKS ---

@router.post("/{task_id}/subtasks", response_model=SubtaskRead)
async def add_subtask(
        task_id: int,
        sub_in: SubtaskCreate,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    task = (await session.execute(
        select(Task).where(Task.id == task_id, Task.family_id == user.family_id))).scalar_one_or_none()
    if not task: raise HTTPException(404)

    sub = Subtask(title=sub_in.title, task_id=task_id)
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub


@router.patch("/subtasks/{sub_id}")
async def toggle_subtask(
        sub_id: int,
        is_done: bool,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    stmt = update(Subtask).where(Subtask.id == sub_id).values(is_done=is_done)
    await session.execute(stmt)
    await session.commit()
    return {"ok": True}
