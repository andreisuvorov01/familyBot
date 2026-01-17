import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aiogram import Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.core.database import engine
from app.core.models.base import Base
from app.bot.handlers.start import router as start_router
from app.api.tasks import router as tasks_router
from app.bot.instance import bot
from app.services.scheduler import send_morning_notifications

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Инициализация FastAPI
app = FastAPI(title="Family Task API")  # <--- ВОТ ТАК ДОЛЖНО БЫТЬ
app.include_router(tasks_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")


# Инициализация диспетчера
dp = Dispatcher()
dp.include_router(start_router)

# Планировщик
scheduler = AsyncIOScheduler()


async def setup_bot_commands(bot):
    commands = [
        types.BotCommand(command="start", description="🏠 Главное меню"),
        types.BotCommand(command="tasks", description="📝 Открыть список дел"),
        types.BotCommand(command="reset", description="🗑 Сброс профиля")
    ]
    await bot.set_my_commands(commands)


async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    scheduler.add_job(send_morning_notifications, "cron", hour=9, minute=0)
    scheduler.start()

    await setup_bot_commands(bot)
    print("Bot and Scheduler started!")


async def main():
    await on_startup()

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)

    await asyncio.gather(server.serve(), dp.start_polling(bot))


if __name__ == "__main__":
    asyncio.run(main())
