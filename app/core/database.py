from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.models.base import Base
from app.core.config import settings

# Асинхронный engine
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# Фабрика сессий
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Функция для получения сессии (для FastAPI Dependency Injection)
async def get_async_session():
    async with async_session_maker() as session:
        yield session
