from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.models.user import User
from app.core.models.Task import Task
from app.core.models.schemas import TaskRead, TaskCreate  # <-- Импортируем TaskCreate
from app.api.security import verify_telegram_data
from app.bot.instance import bot  # <-- Наш бот для уведомлений

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# ... (функция get_tasks остается без изменений) ...

@router.post("/", response_model=TaskRead)
async def create_task(
        task_in: TaskCreate,
        init_data: str = Header(..., alias="X-TG-Data"),
        session: AsyncSession = Depends(get_async_session)
):
    # 1. Авторизация
    user_data = verify_telegram_data(init_data)
    user_tg_id = user_data["id"]

    stmt = select(User).where(User.tg_id == user_tg_id)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user or not user.family_id:
        raise HTTPException(status_code=403, detail="Family not found")

    # 2. Создание задачи
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

    # 3. УВЕДОМЛЕНИЕ ПАРТНЕРА (Магия здесь ✨)
    # Ищем пользователя из ТОЙ ЖЕ семьи, но с ДРУГИМ ID
    partner_stmt = select(User).where(
        User.family_id == user.family_id,
        User.id != user.id
    )
    partner = (await session.execute(partner_stmt)).scalar_one_or_none()

    if partner:
        # Формируем текст уведомления
        emoji = "🤫" if task_in.visibility.value != "common" else "📢"
        text = (
            f"{emoji} <b>Новая задача от партнера!</b>\n"
            f"📌 {task_in.title}\n"
            f"👀 Видимость: {task_in.visibility.value}"
        )
        try:
            await bot.send_message(partner.tg_id, text, parse_mode="HTML")
        except Exception as e:
            print(f"Не удалось отправить пуш партнеру: {e}")

    return new_task
