from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from app.bot.keyboards import get_settings_keyboard, get_role_keyboard
from app.core.models.user import User, TaskCreationMode
from app.core.repositories.user_repository import UserRepository

router = Router()

@router.message(F.text == "⚙️ Настройки")
@router.message(Command("settings"))
async def show_settings(message: types.Message, db_user: User):
    if not db_user:
        return

    await message.answer(
        "⚙️ <b>Настройки профиля</b>\n\n"
        "Здесь вы можете изменить параметры работы бота:",
        reply_markup=get_settings_keyboard(
            db_user.notifications_enabled,
            db_user.task_creation_mode.value
        )
    )

@router.callback_query(F.data == "settings")
async def settings_callback(callback: types.CallbackQuery, db_user: User):
    await callback.message.edit_text(
        "⚙️ <b>Настройки профиля</b>\n\n"
        "Здесь вы можете изменить параметры работы бота:",
        reply_markup=get_settings_keyboard(
            db_user.notifications_enabled,
            db_user.task_creation_mode.value
        )
    )

@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: types.CallbackQuery, db_user: User, user_repo: UserRepository):
    new_state = not db_user.notifications_enabled
    await user_repo.update_settings(db_user.tg_id, notifications_enabled=new_state)
    db_user.notifications_enabled = new_state

    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(
            db_user.notifications_enabled,
            db_user.task_creation_mode.value
        )
    )
    await callback.answer(f"Уведомления {'включены' if new_state else 'выключены'}")

@router.callback_query(F.data == "toggle_creation_mode")
async def toggle_creation_mode(callback: types.CallbackQuery, db_user: User, user_repo: UserRepository):
    new_mode = TaskCreationMode.MESSAGE if db_user.task_creation_mode == TaskCreationMode.COMMAND else TaskCreationMode.COMMAND
    await user_repo.update_settings(db_user.tg_id, task_creation_mode=new_mode)
    db_user.task_creation_mode = new_mode

    await callback.message.edit_reply_markup(
        reply_markup=get_settings_keyboard(
            db_user.notifications_enabled,
            db_user.task_creation_mode.value
        )
    )
    await callback.answer(f"Режим изменен")

@router.callback_query(F.data == "change_role")
async def change_role(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выберите вашу новую роль:",
        reply_markup=get_role_keyboard()
    )

@router.callback_query(F.data == "confirm_reset")
async def confirm_reset(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Да, удалить всё", callback_data="reset_confirmed")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="settings")]
    ])
    await callback.message.edit_text(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Это действие полностью удалит ваш профиль и ВСЕ ваши задачи. Это нельзя будет отменить.\n\n"
        "Вы уверены?",
        reply_markup=keyboard
    )
