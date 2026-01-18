import asyncio
import logging
from aiogram import Dispatcher, types, Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone  # <--- Импорт для часовых поясов

from app.bot.instance import bot
from app.bot.handlers.start import router as start_router
from app.services.scheduler import send_morning_notifications, check_deadlines

# Логирование
logging.basicConfig(level=logging.INFO)

# Диспетчер
dp = Dispatcher()
dp.include_router(start_router)

# Настройка планировщика с Таймзоной
# Указываем, что базовое время планировщика - Москва
scheduler = AsyncIOScheduler(timezone=timezone('Europe/Moscow'))


async def setup_bot_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="🏠 Главное меню"),
        types.BotCommand(command="tasks", description="📝 Открыть список дел"),
        types.BotCommand(command="reset", description="🗑 Сброс профиля"),
    ]
    await bot.set_my_commands(commands)


async def main():
    # 1. Запуск планировщика

    # Утренняя сводка: 09:00 по МОСКВЕ (благодаря настройке выше)
    scheduler.add_job(send_morning_notifications, "cron", hour=9, minute=0)

    # Проверка дедлайнов: Каждую минуту
    # (Тут таймзона не важна, так как интервал относительный)
    scheduler.add_job(check_deadlines, "interval", minutes=1)

    scheduler.start()

    # 2. Настройка меню
    await setup_bot_commands(bot)

    # 3. Запуск поллинга
    print("🤖 Bot started polling with Moscow Timezone...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
