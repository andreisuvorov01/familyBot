import asyncio
from aiogram import Dispatcher, types, Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

from app.bot.instance import bot
from app.bot.handlers.auth.registration import router as registration_router
from app.bot.handlers.auth.family import router as family_router
from app.bot.handlers.tasks.tasks_commands import router as tasks_router
from app.services.scheduler import send_morning_notifications, check_deadlines
from app.core.logging_config import logger, log_with_context

# Диспетчер
dp = Dispatcher()

# Регистрируем роутеры
dp.include_router(registration_router)
dp.include_router(family_router)
dp.include_router(tasks_router)

# Настройка планировщика с Таймзоной
scheduler = AsyncIOScheduler(timezone=timezone('Europe/Moscow'))


async def setup_bot_commands(bot: Bot):
    """Настройка команд бота"""
    commands = [
        types.BotCommand(command="start", description="🏠 Главное меню"),
        types.BotCommand(command="tasks", description="📝 Открыть список дел"),
        types.BotCommand(command="stats", description="📊 Статистика задач"),
        types.BotCommand(command="reset", description="🗑 Сброс профиля"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Bot commands configured")


async def setup_scheduler():
    """Настройка планировщика задач"""
    try:
        # Утренняя сводка: 09:00 по МОСКВЕ
        scheduler.add_job(
            send_morning_notifications,
            "cron",
            hour=9,
            minute=0,
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
        
        scheduler.start()
        logger.info("Scheduler started with 2 jobs")
        
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
        logger.info("🤖 Bot started polling with Moscow Timezone...")
        
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
