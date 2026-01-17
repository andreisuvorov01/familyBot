from aiogram import Bot
from app.core.config import settings

# Инициализируем бота здесь, чтобы импортировать его в любой части проекта
bot = Bot(token=settings.BOT_TOKEN)
