from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.models.base import Base
from app.core.config import settings

database_url = settings.DATABASE_URL
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif not database_url.startswith("postgresql+asyncpg://"):
    raise RuntimeError("FamilyBot now supports PostgreSQL only. Set DATABASE_URL to postgresql+asyncpg://...")

# Асинхронный engine
engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)

# Фабрика сессий
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Функция для получения сессии (для FastAPI Dependency Injection)
async def get_async_session():
    async with async_session_maker() as session:
        yield session
