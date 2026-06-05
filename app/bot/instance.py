from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import os
from app.core.config import settings

def get_bot() -> Bot:
    """Инициализация бота с использованием настроек"""
    token = settings.BOT_TOKEN
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is not set")

    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

# Экспортируем реальный экземпляр бота
bot = get_bot()
