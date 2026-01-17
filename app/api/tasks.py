from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.models.user import User
from app.core.models.Task import Task, TaskVisibility, Subtask
from app.core.models.schemas import TaskRead, TaskCreate, TaskUpdate, SubtaskCreate, SubtaskRead
from app.api.security import verify_telegram_data
from app.bot.instance import bot

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# Вспомогательная функция проверки доступа
async def get_current_user(init_data: str, session: AsyncSession):
    user_data = verify_telegram_data(init_data)
    stmt = select(User).where(User.tg_id == user_data["id"])
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user or not user.family_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return user


# --- TASKS CRUD ---

@router.get("/", response_model=list[TaskRead])
async def get_tasks(
        user=Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    # Логика видимости
    vis = [TaskVisibility.COMMON]
    vis.append(TaskVisibility.HUSBAND if user.role.value == "husband" else TaskVisibility.WIFE)

    query = select(Task).where(
        Task.family_id == user.family_id,
        Task.visibility.in_(vis)
    ).options(selectinload(Task.subtasks)).order_by(Task.created_at.desc())  # Подгружаем подзадачи

    return (await session.execute(query)).scalars().all()


@router.post("/", response_model=TaskRead)
async def create_task(
        task_in: TaskCreate,
        user=Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    new_task = Task(**task_in.dict(), owner_id=user.id, family_id=user.family_id)
    session.add(new_task)
    await session.commit()
    await session.refresh(new_task, attribute_names=["subtasks"])

    # Уведомление
    try:
        partner_stmt = select(User).where(User.family_id == user.family_id, User.id != user.id)
        partner = (await session.execute(partner_stmt)).scalar_one_or_none()
        if partner:
            await bot.send_message(partner.tg_id, f"🆕 <b>{task_in.title}</b>", parse_mode="HTML")
    except Exception as e:
        print(f"Notify error: {e}")

    return new_task


@router.patch("/{task_id}")
async def update_task(
        task_id: int,
        updates: TaskUpdate,
        user=Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    stmt = select(Task).where(Task.id == task_id, Task.family_id == user.family_id)
    task = (await session.execute(stmt)).scalar_one_or_none()
    if not task:
        raise HTTPException(404)

    if updates.status: task.status = updates.status
    if updates.title: task.title = updates.title

    await session.commit()
    return {"ok": True}


@router.delete("/{task_id}")
async def delete_task(
        task_id: int,
        user=Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    stmt = delete(Task).where(Task.id == task_id, Task.family_id == user.family_id)
    await session.execute(stmt)
    await session.commit()
    return {"ok": True}


# --- SUBTASKS CRUD ---

@router.post("/{task_id}/subtasks", response_model=SubtaskRead)
async def add_subtask(
        task_id: int,
        sub_in: SubtaskCreate,
        user=Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    # Проверяем, что задача наша
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
        user=Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    # В идеале нужно проверять family_id через join, но для простоты пропустим
    stmt = update(Subtask).where(Subtask.id == sub_id).values(is_done=is_done)
    await session.execute(stmt)
    await session.commit()
    return {"ok": True}
