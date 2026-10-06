import secrets

from aiogram import Bot, F, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.bot.keyboards import get_family_keyboard, get_main_inline_keyboard, get_main_menu_keyboard, get_role_keyboard
from app.core.logging_config import log_with_context
from app.core.models.user import User, UserRole
from app.core.repositories.user_repository import UserRepository
from app.services.notifications import h, send_safe
from app.services.task_service import TaskService

router = Router()

MAX_FAMILY_SIZE = 2


class FamilyStates(StatesGroup):
    wait_for_code = State()


@router.message(CommandStart())
async def cmd_start(message: types.Message, db_user: User, user_repo: UserRepository):
    if not db_user:
        await user_repo.create(tg_id=message.from_user.id, username=message.from_user.username)
        await message.answer(
            "👋 Привет! Добро пожаловать в семейный органайзер!\n" "Выберите вашу роль:",
            reply_markup=get_role_keyboard(),
        )
    elif not db_user.role:
        await message.answer("Вы еще не выбрали роль:", reply_markup=get_role_keyboard())
    elif not db_user.family_id:
        await message.answer(
            "Роль выбрана! Теперь создайте семью или введите код партнера:", reply_markup=get_family_keyboard()
        )
    else:
        await message.answer("✅ Вы уже в семье и готовы к работе!", reply_markup=get_main_menu_keyboard())
        await message.answer(
            "Воспользуйтесь меню или Mini App для управления задачами.", reply_markup=get_main_inline_keyboard()
        )


@router.callback_query(F.data.startswith("role_"))
async def set_role(callback: types.CallbackQuery, db_user: User, user_repo: UserRepository):
    role_str = callback.data.split("_")[1]
    role = UserRole.HUSBAND if role_str == "husband" else UserRole.WIFE

    await user_repo.update_role(callback.from_user.id, role)

    if not db_user.family_id:
        await callback.message.edit_text(
            f"✅ Роль сохранена!\n" f"Теперь создайте семью или введите код партнера:",
            reply_markup=get_family_keyboard(),
        )
    else:
        await callback.message.edit_text(f"✅ Роль изменена на {role.value}!")
        await callback.message.answer("Главное меню:", reply_markup=get_main_inline_keyboard())


@router.callback_query(F.data == "family_create")
async def create_family(callback: types.CallbackQuery, user_repo: UserRepository):
    family_code = secrets.token_hex(3).upper()
    await user_repo.update_family_id(callback.from_user.id, family_code)

    await callback.message.answer(
        f"✅ <b>Семья создана!</b>\n" f"Передайте этот код партнеру: <code>{family_code}</code>", parse_mode="HTML"
    )

    await callback.message.answer("Готово! Можете приступать к задачам:", reply_markup=get_main_menu_keyboard())
    await callback.message.answer("Управление задачами:", reply_markup=get_main_inline_keyboard())


@router.callback_query(F.data == "family_join")
async def join_family_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите 6-значный код, который вам прислал партнер:")
    await state.set_state(FamilyStates.wait_for_code)


@router.message(FamilyStates.wait_for_code)
async def process_family_code(
    message: types.Message, state: FSMContext, bot: Bot, user_repo: UserRepository, db_user: User
):
    code = message.text.upper().strip()

    if len(code) != 6 or not code.isalnum():
        await message.answer("❌ Код должен состоять из 6 символов. Попробуйте еще раз:")
        return

    # Проверка существования семьи (через любого пользователя с таким family_id)
    # В UserRepository нет прямого метода check_family, используем get_users_by_family
    users_in_family = await user_repo.get_users_by_family(code)

    if not users_in_family:
        await message.answer("❌ Код не найден. Попробуйте еще раз:")
        return

    if db_user.family_id == code:
        await message.answer("🤔 Это ваш собственный код...")
        return

    if len(users_in_family) >= MAX_FAMILY_SIZE:
        await message.answer("❌ В этой семье уже два участника. Попросите партнёра прислать актуальный код.")
        return

    await user_repo.update_family_id(message.from_user.id, code)
    await state.clear()

    await message.answer("🎉 Вы успешно присоединились к семье!", reply_markup=get_main_menu_keyboard())
    await message.answer("Управление задачами:", reply_markup=get_main_inline_keyboard())

    # Уведомление партнеру
    name = f"@{message.from_user.username}" if message.from_user.username else "без имени"
    for partner in users_in_family:
        await send_safe(partner.tg_id, f"🔔 Партнер {h(name)} присоединился к вашей семье!")


@router.callback_query(F.data == "reset_confirmed")
async def reset_confirmed(callback: types.CallbackQuery, db_user: User, session):
    if not db_user:
        await callback.answer()
        return
    # Удаляет задачи пользователя (и их события в Google Calendar), затем профиль
    await TaskService(session).delete_user(db_user)
    await callback.message.edit_text("🗑 Ваш профиль и задачи полностью удалены.\nНажмите /start для новой регистрации.")
