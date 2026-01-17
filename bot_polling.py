import asyncio
from aiogram import Dispatcher
from app.bot.instance import bot
from app.bot.handlers.start import router as start_router
from app.services.scheduler import send_morning_notifications
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Диспетчер и router
dp = Dispatcher()
dp.include_router(start_router)

# Планировщик
scheduler = AsyncIOScheduler()

async def setup_bot_commands(bot):
    from aiogram import types
    commands = [
        types.BotCommand(command="start", description="🏠 Главное меню"),
        types.BotCommand(command="tasks", description="📝 Открыть список дел"),
        types.BotCommand(command="reset", description="🗑 Сброс профиля"),
    ]
    await bot.set_my_commands(commands)

async def main():
    # Запускаем scheduler
    scheduler.add_job(send_morning_notifications, "cron", hour=9, minute=0)
    scheduler.start()

    # Устанавливаем команды
    await setup_bot_commands(bot)

    # Long polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
