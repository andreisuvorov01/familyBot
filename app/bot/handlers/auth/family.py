import secrets
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_maker
from app.core.repositories.user_repository import UserRepository
from app.core.logging_config import log_with_context
from app.core.config import settings
from app.bot.keyboards import get_family_keyboard

router = Router()


class FamilyStates(StatesGroup):
    wait_for_code = State()


@router.callback_query(F.data.startswith("role_"))
async def set_role(callback: types.CallbackQuery):
    """Обработка выбора роли"""
    role_str = callback.data.split("_")[1]
    role = "husband" if role_str == "husband" else "wife"
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        success = await user_repo.update_role(callback.from_user.id, role)
        
        if success:
            await callback.message.edit_text(
                f"✅ Роль сохранена!\n"
                f"Теперь создайте семью или введите код партнера:",
                reply_markup=get_family_keyboard()
            )
            log_with_context(
                "INFO",
                f"Role set: {role}",
                tg_id=callback.from_user.id
            )
        else:
            await callback.answer("❌ Ошибка сохранения роли")


@router.callback_query(F.data == "family_create")
async def create_family(callback: types.CallbackQuery):
    """Создание новой семьи"""
    family_code = secrets.token_hex(3).upper()
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        success = await user_repo.update_family_id(callback.from_user.id, family_code)
        
        if success:
            # Отправляем код
            await callback.message.answer(
                f"✅ <b>Семья создана!</b>\n"
                f"Передайте этот код партнеру: <code>{family_code}</code>",
                parse_mode="HTML"
            )
            
            # Кнопка для веб-приложения
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="📋 Открыть список дел",
                    web_app=WebAppInfo(url=settings.WEBAPP_URL)
                )]
            ])
            
            await callback.message.answer(
                "Готово! Можете приступать к задачам:",
                reply_markup=keyboard
            )
            
            log_with_context(
                "INFO",
                f"Family created: {family_code}",
                tg_id=callback.from_user.id
            )
        else:
            await callback.answer("❌ Ошибка создания семьи")


@router.callback_query(F.data == "family_join")
async def join_family_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало процесса присоединения к семье"""
    await callback.message.answer(
        "Введите 6-значный код, который вам прислал партнер:"
    )
    await state.set_state(FamilyStates.wait_for_code)
    log_with_context(
        "INFO",
        "Family join started",
        tg_id=callback.from_user.id
    )


@router.message(FamilyStates.wait_for_code)
async def process_family_code(
    message: types.Message,
    state: FSMContext,
    bot: Bot
):
    """Обработка кода семьи"""
    code = message.text.upper().strip()
    
    if len(code) != 6 or not code.isalnum():
        await message.answer(
            "❌ Код должен состоять из 6 символов (буквы и цифры).\n"
            "Попробуйте еще раз:"
        )
        return
    
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        
        # Проверяем существование семьи
        stmt = "SELECT * FROM users WHERE family_id = :code"
        users = await session.execute(stmt, {"code": code})
        family_exists = users.scalar_one_or_none() is not None
        
        if not family_exists:
            await message.answer(
                "❌ Код не найден. Попробуйте еще раз:"
            )
            log_with_context(
                "WARNING",
                f"Invalid family code: {code}",
                tg_id=message.from_user.id
            )
            return
        
        # Проверяем, не пытается ли пользователь присоединиться к своей же семье
        current_user = await user_repo.get_by_tg_id(message.from_user.id)
        if current_user and current_user.family_id == code:
            await message.answer(
                "🤔 Это ваш собственный код..."
            )
            return
        
        # Присоединяем к семье
        success = await user_repo.update_family_id(message.from_user.id, code)
        
        if not success:
            await message.answer("❌ Ошибка присоединения к семье")
            return
        
        await state.clear()
        
        # Уведомление текущему пользователю
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📋 Открыть список дел",
                web_app=WebAppInfo(url=settings.WEBAPP_URL)
            )]
        ])
        
        await message.answer(
            "🎉 Вы успешно присоединились к семье!",
            reply_markup=keyboard
        )
        
        # Уведомление партнеру
        try:
            # Находим партнера
            partner_stmt = "SELECT * FROM users WHERE family_id = :code AND tg_id != :tg_id"
            partner = await session.execute(
                partner_stmt,
                {"code": code, "tg_id": message.from_user.id}
            )
            partner_user = partner.scalar_one_or_none()
            
            if partner_user:
                await bot.send_message(
                    partner_user.tg_id,
                    f"🔔 Партнер @{message.from_user.username or 'без имени'} "
                    f"присоединился к вашей семье!"
                )
                
                log_with_context(
                    "INFO",
                    "Partner notified about family join",
                    tg_id=partner_user.tg_id
                )
                
        except Exception as e:
            log_with_context(
                "ERROR",
                f"Failed to notify partner: {str(e)}",
                tg_id=message.from_user.id
            )
        
        log_with_context(
            "INFO",
            f"Joined family: {code}",
            tg_id=message.from_user.id
        )