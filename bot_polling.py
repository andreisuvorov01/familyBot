import asyncio
from aiogram import Dispatcher, types, Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import utc

from app.bot.instance import bot
from app.bot.handlers.auth_handler import router as auth_router
from app.bot.handlers.tasks_handler import router as tasks_router
from app.bot.handlers.settings_handler import router as settings_router
from app.bot.middlewares import DbSessionMiddleware, UserMiddleware
from app.services.scheduler import send_morning_notifications, check_deadlines
from app.services.calendar_sync import process_sync_jobs, pull_calendar_changes
from app.core.logging_config import logger, log_with_context

# Диспетчер
dp = Dispatcher()

# Мидлвари
dp.message.middleware(DbSessionMiddleware())
dp.callback_query.middleware(DbSessionMiddleware())
dp.message.middleware(UserMiddleware())
dp.callback_query.middleware(UserMiddleware())

# Регистрируем роутеры
dp.include_router(auth_router)
dp.include_router(settings_router)
dp.include_router(tasks_router)

# Настройка планировщика с Таймзоной
# Время в заданиях — UTC; пояса пользователей учитываются внутри заданий
scheduler = AsyncIOScheduler(timezone=utc)


async def setup_bot_commands(bot: Bot):
    """Настройка команд бота"""
    commands = [
        types.BotCommand(command="start", description="🏠 Главное меню"),
        types.BotCommand(command="tasks", description="📝 Открыть список дел"),
        types.BotCommand(command="stats", description="📊 Статистика задач"),
        types.BotCommand(command="settings", description="⚙️ Настройки"),
        types.BotCommand(command="help", description="❓ Инструкция"),
        types.BotCommand(command="reset", description="🗑 Сброс профиля"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Bot commands configured")


async def setup_scheduler():
    """Настройка планировщика задач"""
    try:
        # Утренняя сводка: каждые 15 минут, отправляется тем, у кого сейчас 09:00 по их поясу
        scheduler.add_job(
            send_morning_notifications,
            "cron",
            minute="0,15,30,45",
            id="morning_notifications",
            replace_existing=True
        )
        
        # Проверка дедлайнов: Каждую минуту
        scheduler.add_job(
            check_deadlines,
            "interval",
            minutes=1,
            id="deadline_check",
            replace_existing=True
        )
        
        # Google Calendar: отправка изменений (outbox) и забор изменений из календарей
        scheduler.add_job(
            process_sync_jobs,
            "interval",
            seconds=30,
            id="calendar_push",
            replace_existing=True,
            max_instances=1,
        )
        scheduler.add_job(
            pull_calendar_changes,
            "interval",
            minutes=5,
            id="calendar_pull",
            replace_existing=True,
            max_instances=1,
        )

        scheduler.start()
        logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
        
    except Exception as e:
        logger.error(f"Failed to setup scheduler: {str(e)}")
        raise


async def main():
    """Основная функция запуска бота"""
    try:
        # 1. Настройка логирования
        logger.info("Starting Family Bot...")
        
        # 2. Запуск планировщика
        await setup_scheduler()
        
        # 3. Настройка меню команд
        await setup_bot_commands(bot)
        
        # 4. Запуск поллинга
        logger.info("🤖 Bot started polling...")
        
        # Удаляем вебхук и начинаем поллинг
        await bot.delete_webhook(drop_pending_updates=True)
        
        log_with_context(
            "INFO",
            "Bot polling started",
            bot_id=bot.id
        )
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Bot failed to start: {str(e)}")
        raise
    finally:
        # Очистка при завершении
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler stopped")
        
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by keyboard interrupt")
    except SystemExit:
        logger.info("Bot stopped by system exit")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise
