from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


from app.services.scheduler import send_morning_notifications, check_deadlines # <-- Импорт

from app.core.config import settings
from app.core.database import engine
from app.core.models.base import Base
from app.api.tasks import router as tasks_router
from bot_polling import scheduler

# Инициализация приложения
app = FastAPI(title="Family Task API")

# Подключаем роутер задач
app.include_router(tasks_router)

# Подключаем статику (Фронтенд)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Главная страница
@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")

# Событие старта: создание таблиц
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Утро
    scheduler.add_job(send_morning_notifications, "cron", hour=9, minute=0)

    # Проверка дедлайнов КАЖДУЮ МИНУТУ
    scheduler.add_job(check_deadlines, "interval", minutes=1)

    scheduler.start()


