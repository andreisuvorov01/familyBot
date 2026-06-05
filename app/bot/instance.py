from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import os
from app.core.config import settings

_bot_instance: Bot | None = None


def get_bot() -> Bot:
    """Ленивая инициализация бота — не падает при импорте без токена"""
    global _bot_instance
    if _bot_instance is None:
        token = settings.BOT_TOKEN
        if not token:
            raise RuntimeError("BOT_TOKEN environment variable is not set")
        _bot_instance = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
    return _bot_instance


# Совместимость с существующим кодом (bot используется напрямую)
class _LazyBot:
    """Прокси-объект для ленивого доступа к боту"""
    def __getattr__(self, name):
        return getattr(get_bot(), name)

    async def send_message(self, *args, **kwargs):
        return await get_bot().send_message(*args, **kwargs)

    async def get_me(self, *args, **kwargs):
        return await get_bot().get_me(*args, **kwargs)

    async def delete_webhook(self, *args, **kwargs):
        return await get_bot().delete_webhook(*args, **kwargs)

    async def set_my_commands(self, *args, **kwargs):
        return await get_bot().set_my_commands(*args, **kwargs)


bot = _LazyBot()
