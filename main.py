from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import engine
from app.core.models.base import Base
from app.api.tasks import router as tasks_router

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
    print("✅ Database tables checked/created.")

# ВНИМАНИЕ: В конце файла НЕТ uvicorn.run(),
# так как запуск происходит через службу systemd командой 'uvicorn main:app'
