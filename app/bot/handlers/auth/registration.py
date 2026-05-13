from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.repositories.user_repository import UserRepository
from app.core.logging_config import log_with_context
from app.bot.keyboards import get_role_keyboard, get_family_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработка команды /start - регистрация пользователя"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(message.from_user.id)
        
        if not user:
            # Новый пользователь
            user = await user_repo.create(
                tg_id=message.from_user.id,
                username=message.from_user.username
            )
            await message.answer(
                "👋 Привет! Добро пожаловать в семейный органайзер!\n"
                "Выберите вашу роль:",
                reply_markup=get_role_keyboard()
            )
            log_with_context(
                "INFO",
                "New user registered",
                user_id=user.id,
                tg_id=message.from_user.id
            )
            
        elif not user.role:
            # Пользователь без роли
            await message.answer(
                "Вы еще не выбрали роль:",
                reply_markup=get_role_keyboard()
            )
            
        elif not user.family_id:
            # Пользователь без семьи
            await message.answer(
                "Роль выбрана! Теперь создайте семью или введите код партнера:",
                reply_markup=get_family_keyboard()
            )
            
        else:
            # Пользователь уже зарегистрирован
            await message.answer(
                "✅ Вы уже в семье и готовы к работе!\n"
                "Используйте /tasks для управления задачами."
            )
            log_with_context(
                "INFO",
                "Returning user",
                user_id=user.id,
                family_id=user.family_id
            )