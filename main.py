import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aiogram import Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # <-- Импорт шедулера

from app.core.config import settings
from app.core.database import engine
from app.core.models.base import Base
from app.bot.handlers.start import router as start_router
from app.api.tasks import router as tasks_router
from app.bot.instance import bot  # <-- Импорт бота из instance
from app.services.scheduler import send_morning_notifications  # <-- Наша функция

# ... (настройка FastAPI и логгера такая же) ...
app = FastAPI(...)
app.include_router(tasks_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")


dp = Dispatcher()
dp.include_router(start_router)

# Настройка планировщика
scheduler = AsyncIOScheduler()


async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Запускаем задачу каждое утро в 09:00
    scheduler.add_job(send_morning_notifications, "cron", hour=9, minute=0)
    scheduler.start()

    print("Scheduler started!")


# ... (setup_bot_commands и остальное без изменений) ...

async def main():
    await on_startup()  # <-- Вызываем setup здесь

    # Запуск API и Бота
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)

    await asyncio.gather(server.serve(), dp.start_polling(bot))


if __name__ == "__main__":
    asyncio.run(main())
