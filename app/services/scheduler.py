from datetime import datetime, timedelta
from sqlalchemy import select, update
from app.core.database import async_session_maker
from app.core.models.user import User
from app.core.models.Task import Task
from app.bot.instance import bot


# 1. Утренняя сводка (как было)
async def send_morning_notifications():
    async with async_session_maker() as session:
        users = (await session.execute(select(User))).scalars().all()
        for user in users:
            stmt = select(Task).where(Task.family_id == user.family_id, Task.status == "pending")
            tasks = (await session.execute(stmt)).scalars().all()
            if tasks:
                await bot.send_message(user.tg_id, f"☕ Доброе утро! Задач на сегодня: {len(tasks)}.")


# 2. Проверка дедлайнов (НОВОЕ)
async def check_deadlines():
    async with async_session_maker() as session:
        now = datetime.utcnow()  # Важно: время сервера (UTC)

        # Ищем задачи, которые:
        # 1. Не выполнены
        # 2. Имеют дедлайн
        # 3. Дедлайн уже прошел ИЛИ наступит в ближайшие 30 минут
        # 4. Напоминание еще НЕ отправлено

        # Условие: deadline < (now + 30 min)
        target_time = now + timedelta(minutes=30)

        query = select(Task).where(
            Task.status == "pending",
            Task.deadline != None,
            Task.deadline <= target_time,
            Task.reminder_sent == False
        )

        tasks = (await session.execute(query)).scalars().all()

        for task in tasks:
            # Получаем владельца, чтобы узнать chat_id
            user = await session.get(User, task.owner_id)
            if not user: continue

            # Текст уведомления
            is_expired = task.deadline < now
            if is_expired:
                text = f"🔥 <b>Дедлайн пропущен!</b>\nЗадача: {task.title}"
            else:
                text = f"⏰ <b>Скоро дедлайн!</b>\nЗадача: {task.title}\nОсталось меньше 30 минут."

            try:
                # Шлем владельцу
                await bot.send_message(user.tg_id, text, parse_mode="HTML")

                # Если задача общая - шлем и партнеру
                if task.visibility.value == "common":
                    partner_stmt = select(User).where(User.family_id == user.family_id, User.id != user.id)
                    partner = (await session.execute(partner_stmt)).scalar_one_or_none()
                    if partner:
                        await bot.send_message(partner.tg_id, text, parse_mode="HTML")
            except Exception:
                pass

            # Помечаем, что напомнили
            task.reminder_sent = True

        await session.commit()
