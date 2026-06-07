import asyncio
import sys
import os

# Добавляем корневую директорию проекта в sys.path, чтобы импорт app работал
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import engine
from app.core.logging_config import logger

async def update_schema():
    """
    Скрипт для обновления схемы БД:
    - Добавление morning_summary_enabled в таблицу users
    - Добавление priority в таблицу tasks
    """
    logger.info("Starting schema update...")

    async with engine.begin() as conn:
        # 1. Добавляем morning_summary_enabled в users
        try:
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS morning_summary_enabled BOOLEAN DEFAULT TRUE"
            ))
            logger.info("Added morning_summary_enabled to users table")
        except Exception as e:
            logger.warning(f"Could not add morning_summary_enabled: {e}")

        # 2. Добавляем priority в tasks
        try:
            await conn.execute(text(
                "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority VARCHAR(20)"
            ))
            logger.info("Added priority to tasks table")
        except Exception as e:
            logger.warning(f"Could not add priority: {e}")

    await engine.dispose()
    logger.info("Schema update completed successfully")

if __name__ == "__main__":
    asyncio.run(update_schema())
