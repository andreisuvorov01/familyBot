"""Интеграционные тесты на реальном PostgreSQL (DATABASE_URL).

Запуск: INTEGRATION_DB=1 pytest tests/integration — база будет очищена!
"""
import asyncio
import hashlib
import hmac
import json
import os
import time
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
import pytest_asyncio

if os.getenv("INTEGRATION_DB") != "1":
    pytest.skip("set INTEGRATION_DB=1 to run integration tests", allow_module_level=True)

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import async_session_maker, engine  # noqa: E402
from app.core.migrations import run_migrations  # noqa: E402
from app.core.models.user import User, UserRole  # noqa: E402


def make_init_data(tg_id: int, username: str = "user") -> str:
    """Подписанный initData, как его формирует Telegram."""
    vals = {
        "auth_date": str(int(time.time())),
        "query_id": "test",
        "user": json.dumps({"id": tg_id, "first_name": username, "username": username}),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(vals.items()))
    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    vals["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(vals)


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    async def reset():
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await engine.dispose()

    asyncio.run(reset())
    run_migrations()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(monkeypatch):
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE calendar_sync_jobs, task_calendar_events, google_accounts, task_completions, "
            "subtasks, tasks, users RESTART IDENTITY CASCADE"
        ))
    from app.core.security.rate_limiter import rate_limiter
    rate_limiter.requests.clear()
    sent = AsyncMock()
    monkeypatch.setattr("app.bot.instance.bot.send_message", sent)
    yield sent
    await engine.dispose()


@pytest_asyncio.fixture
async def family():
    async with async_session_maker() as session:
        husband = User(tg_id=101, username="husband", role=UserRole.HUSBAND, family_id="ABC123")
        wife = User(tg_id=202, username="wife", role=UserRole.WIFE, family_id="ABC123", timezone="Asia/Yekaterinburg")
        session.add_all([husband, wife])
        await session.commit()
        return husband, wife


@pytest_asyncio.fixture
async def client():
    from main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def auth(tg_id: int) -> dict:
    return {"X-TG-Data": make_init_data(tg_id)}
