from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session
from app.core.models.user import User, UserRole
from app.core.models.Task import Task, TaskVisibility
from app.core.models.schemas import TaskRead
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from app.api.security import verify_telegram_data
router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("/")
async def get_tasks(
        init_data: str = Header(..., alias="X-TG-Data"),  # Передаем в кастомном заголовке
        session: AsyncSession = Depends(get_async_session)
):
    user_info = verify_telegram_data(init_data)
    tg_id = user_info.get("id")

    # Получаем юзера из БД, чтобы узнать его family_id и role
    user_stmt = select(User).where(User.tg_id == tg_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()

    if not user or not user.family_id:
        raise HTTPException(status_code=404, detail="User not in family")

    # Фильтруем задачи по family_id И видимости
    visibilities = [TaskVisibility.COMMON]
    visibilities.append(TaskVisibility.HUSBAND if user.role == UserRole.HUSBAND else TaskVisibility.WIFE)

    query = select(Task).where(
        Task.family_id == user.family_id,
        Task.visibility.in_(visibilities)
    )

    result = await session.execute(query)
    return result.scalars().all()
