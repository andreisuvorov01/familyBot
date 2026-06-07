import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path, чтобы импорт app работал
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Пытаемся загрузить .env вручную перед импортом настроек
try:
    from dotenv import load_dotenv
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"Loaded .env from {env_path}")
    else:
        print(f"Warning: .env file not found at {env_path}")
except ImportError:
    print("Warning: python-dotenv not installed, skipping manual .env load")

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
