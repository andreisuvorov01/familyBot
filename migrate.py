"""
Скрипт миграции базы данных.
Создаёт/обновляет таблицы через SQLAlchemy metadata.
Поддерживает как SQLite, так и PostgreSQL через DATABASE_URL.
"""
import asyncio
import os
import sys


async def run_migrations():
    from app.core.database import engine
    from app.core.models.base import Base
    # Импортируем все модели чтобы они зарегистрировались в metadata
    from app.core.models import Task, User  # noqa: F401

    print(f"Running migrations for: {os.getenv('DATABASE_URL', 'sqlite').split('@')[-1]}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Migrations completed successfully")
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_migrations())
