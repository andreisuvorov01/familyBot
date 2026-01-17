# app/services/scheduler.py
from sqlalchemy import select, func
from app.core.database import async_session_maker
from app.core.models.user import User
from app.core.models.Task import Task
from app.bot.instance import bot


async def send_morning_notifications():
    async with async_session_maker() as session:
        # Получаем всех пользователей
        users = (await session.execute(select(User))).scalars().all()

        for user in users:
            # Считаем количество активных (pending) задач для этого юзера
            # (Логика упрощена: берем все общие + личные)
            stmt = select(func.count(Task.id)).where(
                Task.family_id == user.family_id,
                Task.status == "pending"
            )
            count = (await session.execute(stmt)).scalar()

            if count > 0:
                try:
                    await bot.send_message(
                        user.tg_id,
                        f"☕ Доброе утро! На сегодня у вашей семьи <b>{count} задач</b>.\nЗагляните в Mini App!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass  # Юзер мог заблокировать бота