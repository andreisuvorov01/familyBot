import asyncio
import uvicorn
from fastapi import FastAPI
from aiogram import Bot, Dispatcher
from app.core.config import settings
from app.core.database import engine
from app.core.models.base import Base
from fastapi.middleware.cors import CORSMiddleware
from app.bot.handlers.start import router as start_router
from app.api.tasks import router as tasks_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
# Инициализация FastAPI
app = FastAPI(title="Family Task API")
app.include_router(tasks_router)
app.add_middleware(
    CORSMiddleware,
    # Укажи здесь адрес, где будет лежать твой фронтенд (например, Vercel или твой домен)
    # Для разработки можно оставить ["*"], но в продакшене — только конкретный домен
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
# Инициализация Bot
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()
dp.include_router(start_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")
async def run_bot():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await dp.start_polling(bot)

async def run_api():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # Запускаем бота и API одновременно
    await asyncio.gather(run_bot(), run_api())

if __name__ == "__main__":
    asyncio.run(main())
