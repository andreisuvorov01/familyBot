from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Tuple
from sqlalchemy import select
from app.core.database import async_session_maker
from app.core.models.user import User
from app.core.models.Task import Task, TaskVisibility
from app.core.repositories.user_repository import UserRepository
from app.core.repositories.task_repository import TaskRepository
from app.core.logging_config import log_with_context, logger
from app.bot.instance import bot


async def send_morning_notifications():
    """Утренняя сводка задач (оптимизированная версия)"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        
        # Получаем всех пользователей с семьями
        stmt = select(User).where(User.family_id != None)
        users = (await session.execute(stmt)).scalars().all()
        
        notifications_sent = 0
        errors = 0
        
        for user in users:
            try:
                # Получаем задачи семьи одним запросом
                tasks = await task_repo.get_pending_tasks_by_family(user.family_id)
                
                if tasks:
                    # Группируем задачи по типам
                    personal_tasks = [t for t in tasks if t.visibility != TaskVisibility.COMMON]
                    common_tasks = [t for t in tasks if t.visibility == TaskVisibility.COMMON]
                    
                    message = f"☕ Доброе утро!\n"
                    message += f"📋 Всего задач: {len(tasks)}\n"
                    
                    if personal_tasks:
                        message += f"• Личных: {len(personal_tasks)}\n"
                    if common_tasks:
                        message += f"• Общих: {len(common_tasks)}\n"
                    
                    # Добавляем задачи с дедлайнами сегодня (по Московскому времени)
                    tz_moscow = pytz.timezone('Europe/Moscow')
                    today_moscow = datetime.now(tz_moscow).date()

                    today_tasks = []
                    for t in tasks:
                        if t.deadline:
                            # t.deadline в БД хранится в UTC (naive)
                            deadline_utc = pytz.UTC.localize(t.deadline)
                            deadline_moscow = deadline_utc.astimezone(tz_moscow)
                            if deadline_moscow.date() == today_moscow:
                                today_tasks.append(t)
                    
                    if today_tasks:
                        message += f"\n⏰ Сегодня дедлайн у {len(today_tasks)} задач"
                    
                    await bot.send_message(user.tg_id, message)
                    notifications_sent += 1
                    
                    log_with_context(
                        "INFO",
                        f"Morning notification sent: {len(tasks)} tasks",
                        user_id=user.id,
                        family_id=user.family_id
                    )
                    
            except Exception as e:
                errors += 1
                log_with_context(
                    "ERROR",
                    f"Failed to send morning notification: {str(e)}",
                    user_id=user.id
                )
        
        logger.info(
            f"Morning notifications completed: {notifications_sent} sent, {errors} errors"
        )


async def check_deadlines():
    """Проверка дедлайнов с batch обработкой"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        
        now = datetime.utcnow()
        target_time = now + timedelta(minutes=30)
        
        # Получаем все задачи с приближающимися дедлайнами
        tasks = await task_repo.get_pending_tasks_with_deadlines(target_time)
        
        if not tasks:
            logger.debug("No tasks with approaching deadlines")
            return
        
        # Группируем задачи по владельцам
        tasks_by_owner: Dict[int, List[Task]] = {}
        for task in tasks:
            if task.owner_id not in tasks_by_owner:
                tasks_by_owner[task.owner_id] = []
            tasks_by_owner[task.owner_id].append(task)
        
        # Получаем информацию о пользователях одним запросом
        owner_ids = list(tasks_by_owner.keys())
        stmt = select(User).where(User.id.in_(owner_ids))
        users = (await session.execute(stmt)).scalars().all()
        user_map = {user.id: user for user in users}
        
        notifications_sent = 0
        errors = 0
        
        # Обрабатываем з��дачи batch'ами
        for owner_id, owner_tasks in tasks_by_owner.items():
            user = user_map.get(owner_id)
            if not user:
                continue
            
            try:
                # Группируем задачи по типам уведомлений
                expired_tasks = []
                upcoming_tasks = []
                
                for task in owner_tasks:
                    is_expired = task.deadline < now
                    if is_expired:
                        expired_tasks.append(task)
                    else:
                        upcoming_tasks.append(task)
                
                # Отправляем уведомления владельцу
                if expired_tasks:
                    await send_expired_notification(user, expired_tasks)
                    notifications_sent += 1
                
                if upcoming_tasks:
                    await send_upcoming_notification(user, upcoming_tasks)
                    notifications_sent += 1
                
                # Отправляем уведомления партнерам для общих задач
                common_tasks = [t for t in owner_tasks if t.visibility == TaskVisibility.COMMON]
                if common_tasks:
                    partner = await user_repo.get_partner(user)
                    if partner:
                        if expired_tasks:
                            await send_expired_notification(partner, expired_tasks, is_partner=True)
                        if upcoming_tasks:
                            await send_upcoming_notification(partner, upcoming_tasks, is_partner=True)
                
                # Помечаем задачи как уведомленные
                for task in owner_tasks:
                    task.reminder_sent = True
                
                log_with_context(
                    "INFO",
                    f"Deadline notifications processed: {len(owner_tasks)} tasks",
                    user_id=user.id,
                    family_id=user.family_id
                )
                
            except Exception as e:
                errors += 1
                log_with_context(
                    "ERROR",
                    f"Failed to process deadline notifications: {str(e)}",
                    user_id=user.id
                )
        
        # Сохраняем изменения в БД
        await session.commit()
        
        logger.info(
            f"Deadline check completed: {len(tasks)} tasks processed, "
            f"{notifications_sent} notifications sent, {errors} errors"
        )


async def send_expired_notification(
    user: User,
    tasks: List[Task],
    is_partner: bool = False
):
    """Отправить уведомление о просроченных задачах"""
    if not tasks:
        return
    
    prefix = "🔔 Партнер пропустил дедлайн!\n" if is_partner else "🔥 <b>Дедлайн пропущен!</b>\n"
    
    if len(tasks) == 1:
        task = tasks[0]
        message = f"{prefix}Задача: {task.title}"
    else:
        task_list = "\n".join([f"• {task.title}" for task in tasks[:5]])
        if len(tasks) > 5:
            task_list += f"\n• ...и еще {len(tasks) - 5}"
        message = f"{prefix}Просроченные задачи:\n{task_list}"
    
    await bot.send_message(user.tg_id, message, parse_mode="HTML")


async def send_upcoming_notification(
    user: User,
    tasks: List[Task],
    is_partner: bool = False
):
    """Отправить уведомление о приближающихся дедлайнах"""
    if not tasks:
        return
    
    prefix = "🔔 У партнера скоро дедлайн!\n" if is_partner else "⏰ <b>Скоро дедлайн!</b>\n"
    
    if len(tasks) == 1:
        task = tasks[0]
        # Оба времени в UTC для корректного вычисления разницы
        time_left = task.deadline - datetime.utcnow()
        minutes_left = max(0, int(time_left.total_seconds() / 60))
        message = f"{prefix}Задача: {task.title}\nОсталось: {minutes_left} минут"
    else:
        task_list = "\n".join([f"• {task.title}" for task in tasks[:5]])
        if len(tasks) > 5:
            task_list += f"\n• ...и еще {len(tasks) - 5}"
        message = f"{prefix}Скоро дедлайн у задач:\n{task_list}\nОсталось меньше 30 минут"
    
    await bot.send_message(user.tg_id, message, parse_mode="HTML")
