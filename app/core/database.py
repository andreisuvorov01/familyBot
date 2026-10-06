from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings


def normalize_database_url(url: str) -> str:
    """Приводит DATABASE_URL к драйверу asyncpg (поддерживается только PostgreSQL)."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url
    raise RuntimeError("FamilyBot now supports PostgreSQL only. Set DATABASE_URL to postgresql+asyncpg://...")


database_url = normalize_database_url(settings.DATABASE_URL)

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
