from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.models.user import User, UserRole
from app.core.models.Task import Task, TaskVisibility
from app.core.models.schemas import TaskRead, TaskCreate
from app.api.security import verify_telegram_data
from app.bot.instance import bot

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# --- GET: Получение списка ---
@router.get("/", response_model=list[TaskRead])
async def get_tasks(
        init_data: str = Header(..., alias="X-TG-Data"),
        session: AsyncSession = Depends(get_async_session)
):
    user_data = verify_telegram_data(init_data)
    user_tg_id = user_data["id"]

    stmt = select(User).where(User.tg_id == user_tg_id)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user or not user.family_id:
        return []

    visibilities = [TaskVisibility.COMMON]
    visibilities.append(TaskVisibility.HUSBAND if user.role == UserRole.HUSBAND else TaskVisibility.WIFE)

    query = select(Task).where(
        Task.family_id == user.family_id,
        Task.visibility.in_(visibilities)
    ).order_by(Task.created_at.desc())

    result = await session.execute(query)
    return result.scalars().all()


# --- POST: Создание задачи (Именно этого не хватало) ---
@router.post("/", response_model=TaskRead)
async def create_task(
        task_in: TaskCreate,
        init_data: str = Header(..., alias="X-TG-Data"),
        session: AsyncSession = Depends(get_async_session)
):
    # 1. Проверяем юзера
    user_data = verify_telegram_data(init_data)
    user_tg_id = user_data["id"]

    stmt = select(User).where(User.tg_id == user_tg_id)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user or not user.family_id:
        raise HTTPException(status_code=403, detail="No family found")

    # 2. Создаем задачу
    new_task = Task(
        title=task_in.title,
        description=task_in.description,
        visibility=task_in.visibility,
        owner_id=user.id,
        family_id=user.family_id
    )
    session.add(new_task)
    await session.commit()
    await session.refresh(new_task)

    # 3. Уведомляем партнера
    try:
        partner_stmt = select(User).where(
            User.family_id == user.family_id,
            User.id != user.id
        )
        partner = (await session.execute(partner_stmt)).scalar_one_or_none()

        if partner:
            text = f"📢 <b>Новая задача!</b>\n{task_in.title}"
            await bot.send_message(partner.tg_id, text, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка уведомления: {e}")

    return new_task