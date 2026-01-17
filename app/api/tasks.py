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


# Вспомогательная функция (Dependency)
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


# --- TASKS ---

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
    new_task = Task(
        title=task_in.title,
        description=task_in.description,
        visibility=task_in.visibility,
        owner_id=user.id,
        family_id=user.family_id
    )
    session.add(new_task)
    await session.commit()
    await session.refresh(new_task, attribute_names=["subtasks"])

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
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    stmt = select(Task).where(Task.id == task_id, Task.family_id == user.family_id)
    task = (await session.execute(stmt)).scalar_one_or_none()
    if not task: raise HTTPException(404)

    if updates.status: task.status = updates.status
    if updates.title: task.title = updates.title

    await session.commit()
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
