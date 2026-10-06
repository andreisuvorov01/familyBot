"""Применение миграций Alembic.

Раньше схема создавалась через Base.metadata.create_all() (+ scripts/update_schema.py),
поэтому у существующих баз нет таблицы alembic_version. Такие базы сначала
«чинятся» до состояния ревизии 0001 и помечаются ею, а затем обновляются как обычно.
"""
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.database import normalize_database_url
from app.core.logging_config import logger

BASE_DIR = Path(__file__).resolve().parents[2]
BASELINE_REVISION = "0001"

# Идемпотентно доводим «старую» схему до ревизии 0001
LEGACY_REPAIR_SQL = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS morning_summary_enabled BOOLEAN NOT NULL DEFAULT TRUE",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taskpriority') THEN
            CREATE TYPE taskpriority AS ENUM ('LOW', 'MEDIUM', 'HIGH');
        END IF;
    END$$
    """,
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority taskpriority",
]


def _alembic_config() -> Config:
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    return cfg


def _is_legacy_database() -> bool:
    """True, если таблицы есть, а версии Alembic нет."""
    async def check() -> bool:
        engine = create_async_engine(normalize_database_url(settings.DATABASE_URL))
        try:
            async with engine.begin() as conn:
                tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
                if "users" in tables and "alembic_version" not in tables:
                    for statement in LEGACY_REPAIR_SQL:
                        await conn.execute(text(statement))
                    return True
                return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


def run_migrations() -> None:
    """Синхронная функция: вызывать из отдельного потока, если event loop уже запущен."""
    cfg = _alembic_config()
    if _is_legacy_database():
        logger.info("Legacy database detected: stamping baseline revision %s", BASELINE_REVISION)
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")
    logger.info("Database migrations applied")
