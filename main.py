import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from aiogram import Bot, Dispatcher, types  # <-- Добавлен types
from app.core.config import settings
from app.core.database import engine
from app.core.models.base import Base
from app.bot.handlers.start import router as start_router
from app.api.tasks import router as tasks_router

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация FastAPI
app = FastAPI(title="Family Task API")
app.include_router(tasks_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")


# Инициализация бота
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
dp.include_router(start_router)


# --- НОВАЯ ФУНКЦИЯ ДЛЯ МЕНЮ ---
async def setup_bot_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="🏠 Главное меню"),
        types.BotCommand(command="tasks", description="📝 Открыть список дел"),  # Мы сейчас сделаем этот хендлер
        types.BotCommand(command="reset", description="🗑 Сброс профиля")
    ]
    await bot.set_my_commands(commands)


# ------------------------------

async def run_bot():
    # Создаем таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Устанавливаем команды меню
    await setup_bot_commands(bot)

    print("Bot started with menu!")
    await dp.start_polling(bot)


async def run_api():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await asyncio.gather(run_bot(), run_api())


if __name__ == "__main__":
    asyncio.run(main())
