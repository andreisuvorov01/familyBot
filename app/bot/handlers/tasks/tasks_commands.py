from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.repositories.user_repository import UserRepository
from app.core.repositories.task_repository import TaskRepository
from app.core.logging_config import log_with_context
from app.core.config import settings
from app.core.models.Task import Task

router = Router()


@router.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    """Открытие веб-приложения с задачами"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Открыть список дел",
            web_app=WebAppInfo(url=settings.WEBAPP_URL)
        )]
    ])
    
    await message.answer(
        "Вот ваши задачи:",
        reply_markup=keyboard
    )
    
    log_with_context(
        "INFO",
        "Tasks command executed",
        tg_id=message.from_user.id
    )


@router.message(F.text == "Открыть задачи")
async def show_main_menu(message: types.Message):
    """Альтернативный способ открытия задач"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Список дел",
            web_app=WebAppInfo(url=settings.WEBAPP_URL)
        )]
    ])
    
    await message.answer(
        "Ваш семейный органайзер готов!",
        reply_markup=keyboard
    )


@router.message(Command("reset"))
async def cmd_reset(message: types.Message):
    """Сброс профиля пользователя"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        
        # Получаем пользователя
        user = await user_repo.get_by_tg_id(message.from_user.id)
        
        if not user:
            await message.answer("Вы и так не зарегистрированы.")
            return
        
        # Удаляем все задачи пользователя
        if user.family_id:
            tasks = await task_repo.get_family_tasks(user.family_id, user.role)
            for task in tasks:
                if task.owner_id == user.id:
                    await task_repo.delete_task(task.id, user.family_id)
        
        # Удаляем пользователя
        success = await user_repo.delete_user(message.from_user.id)
        
        if success:
            await message.answer(
                "🗑 Ваш профиль и задачи полностью удалены.\n"
                "Нажмите /start для новой регистрации."
            )
            
            log_with_context(
                "INFO",
                "User profile reset",
                tg_id=message.from_user.id
            )
        else:
            await message.answer("❌ Ошибка при сбросе профиля")


@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Статистика по задачам"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)
        
        user = await user_repo.get_by_tg_id(message.from_user.id)
        
        if not user or not user.family_id:
            await message.answer(
                "Сначала зарегистрируйтесь с помощью /start"
            )
            return
        
        # Получаем статистику
        tasks = await task_repo.get_family_tasks(user.family_id, user.role)
        
        if not tasks:
            await message.answer("📊 У вас пока нет задач.")
            return
        
        # Анализируем задачи
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.status == "done"])
        pending_tasks = total_tasks - completed_tasks
        
        # Задачи с дедлайнами
        tasks_with_deadlines = len([t for t in tasks if t.deadline])
        
        # Просроченные задачи
        from datetime import datetime
        now = datetime.utcnow()
        overdue_tasks = len([
            t for t in tasks 
            if t.deadline and t.deadline < now and t.status != "done"
        ])
        
        # Формируем сообщение
        stats_message = (
            f"📊 <b>Статистика задач</b>\n\n"
            f"• Всего задач: {total_tasks}\n"
            f"• Выполнено: {completed_tasks}\n"
            f"• В работе: {pending_tasks}\n"
            f"• С дедлайнами: {tasks_with_deadlines}\n"
            f"• Просрочено: {overdue_tasks}\n"
        )
        
        if completed_tasks > 0:
            completion_rate = (completed_tasks / total_tasks) * 100
            stats_message += f"• Процент выполнения: {completion_rate:.1f}%\n"
        
        await message.answer(stats_message, parse_mode="HTML")
        
        log_with_context(
            "INFO",
            f"Stats viewed: {total_tasks} tasks",
            user_id=user.id,
            family_id=user.family_id
        )