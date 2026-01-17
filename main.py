from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import engine
from app.core.models.base import Base
from app.api.tasks import router as tasks_router

# Инициализация FastAPI
app = FastAPI(title="Family Task API")

app.include_router(tasks_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def serve_spa():
    return FileResponse("app/static/index.html")

# Применяем миграции при старте (если нужно)
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
