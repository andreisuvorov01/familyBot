import secrets
from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select, update
from aiogram.types import WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import delete
from aiogram.filters import Command
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.models import Task
from app.core.models.user import User, UserRole
from app.bot.keyboards import get_role_keyboard, get_family_keyboard

router = Router()


# Состояния для ввода кода
class FamilyStates(StatesGroup):
    wait_for_code = State()
@router.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    # Просто показываем кнопку, так как это единственная точка входа
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Открыть список дел",
            web_app=WebAppInfo(url=settings.WEBAPP_URL)
        )]
    ])
    await message.answer("Вот ваши задачи:", reply_markup=keyboard)

@router.message(F.text == "Открыть задачи" or CommandStart())
async def show_main_menu(message: types.Message):
    # ЗАМЕНИ URL на адрес своего сервера (например, через ngrok для тестов)
    web_app=WebAppInfo(url=settings.WEBAPP_URL)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список дел", web_app=WebAppInfo(url=settings.WEBAPP_URL))]
    ])

    await message.answer("Ваш семейный органайзер готов!", reply_markup=keyboard)
@router.message(CommandStart())
async def cmd_start(message: types.Message):
    async with async_session_maker() as session:
        stmt = select(User).where(User.tg_id == message.from_user.id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            new_user = User(tg_id=message.from_user.id, username=message.from_user.username)
            session.add(new_user)
            await session.commit()
            await message.answer("Привет! Выберите вашу роль:", reply_markup=get_role_keyboard())
        elif not user.role:
            await message.answer("Вы еще не выбрали роль:", reply_markup=get_role_keyboard())
        elif not user.family_id:
            await message.answer("Роль выбрана. Теперь создайте семью или введите код партнера:",
                                 reply_markup=get_family_keyboard())
        else:
            await message.answer("✅ Вы уже в семье и готовы к работе!")


@router.message(Command("reset"))
async def cmd_reset(message: types.Message):
    async with async_session_maker() as session:
        # 1. Находим пользователя
        stmt = select(User).where(User.tg_id == message.from_user.id)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if user:
            # 2. Удаляем все его задачи
            await session.execute(delete(Task).where(Task.owner_id == user.id))

            # 3. Удаляем самого пользователя
            await session.delete(user)
            await session.commit()

            await message.answer("🗑 Ваш профиль и задачи полностью удалены. Нажмите /start для новой регистрации.")
        else:
            await message.answer("Вы и так не зарегистрированы.")

@router.callback_query(F.data.startswith("role_"))
async def set_role(callback: types.CallbackQuery):
    role_str = callback.data.split("_")[1]
    role = UserRole.HUSBAND if role_str == "husband" else UserRole.WIFE

    async with async_session_maker() as session:
        stmt = update(User).where(User.tg_id == callback.from_user.id).values(role=role)
        await session.execute(stmt)
        await session.commit()

    await callback.message.edit_text(f"Роль сохранена! Теперь создайте семью или введите код.",
                                     reply_markup=get_family_keyboard())


@router.callback_query(F.data == "family_create")
async def create_family(callback: types.CallbackQuery):
    family_code = secrets.token_hex(3).upper()
    async with async_session_maker() as session:
        stmt = update(User).where(User.tg_id == callback.from_user.id).values(family_id=family_code)
        await session.execute(stmt)
        await session.commit()

    await callback.message.answer(
        f"Ваша семья создана! \nПередайте этот код партнеру: <code>{family_code}</code>",
        parse_mode="HTML"
    )


# --- ЛОГИКА ПРИСОЕДИНЕНИЯ ---

@router.callback_query(F.data == "family_join")
async def join_family_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите 6-значный код, который вам прислал партнер:")
    await state.set_state(FamilyStates.wait_for_code)


@router.message(FamilyStates.wait_for_code)
async def process_family_code(message: types.Message, state: FSMContext, bot: Bot):
    code = message.text.upper().strip()

    async with async_session_maker() as session:
        # Ищем партнера, у которого такой же код
        stmt = select(User).where(User.family_id == code)
        partner = (await session.execute(stmt)).scalar_one_or_none()

        if not partner:
            await message.answer("❌ Код не найден. Попробуйте еще раз или создайте свою семью.")
            return

        if partner.tg_id == message.from_user.id:
            await message.answer("🤔 Это ваш собственный код...")
            return

        # Обновляем family_id текущего пользователя
        stmt_update = update(User).where(User.tg_id == message.from_user.id).values(family_id=code)
        await session.execute(stmt_update)
        await session.commit()

        # Завершаем состояние
        await state.clear()

        # Уведомляем обоих
        await message.answer("🎉 Ура! Вы успешно связали аккаунты!")
        try:
            await bot.send_message(partner.tg_id,
                                   f"🔔 Партнер @{message.from_user.username} присоединился к вашей семье!")
        except Exception:
            pass  # Если партнер заблокировал бота
