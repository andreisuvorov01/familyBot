from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from app.core.config import settings

def get_role_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🙋‍♂️ Я Муж", callback_data="role_husband")],
        [InlineKeyboardButton(text="🙋‍♀️ Я Жена", callback_data="role_wife")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_family_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🏠 Создать семью", callback_data="family_create")],
        [InlineKeyboardButton(text="🔑 Ввести код партнера", callback_data="family_join")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_menu_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Список дел", web_app=WebAppInfo(url=settings.WEBAPP_URL))],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_main_inline_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Открыть Mini App", web_app=WebAppInfo(url=settings.WEBAPP_URL))],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
             InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
            [InlineKeyboardButton(text="❓ Инструкция", callback_data="help")]
        ]
    )
    return keyboard

def get_settings_keyboard(notifications_enabled: bool, creation_mode: str):
    notif_text = "🔔 Уведомления: ВКЛ" if notifications_enabled else "🔕 Уведомления: ВЫКЛ"
    mode_text = "✍️ Режим: Сообщения" if creation_mode == "message" else "💬 Режим: Команды"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=notif_text, callback_data="toggle_notifications")],
            [InlineKeyboardButton(text=mode_text, callback_data="toggle_creation_mode")],
            [InlineKeyboardButton(text="👤 Изменить роль", callback_data="change_role")],
            [InlineKeyboardButton(text="🔄 Сброс профиля", callback_data="confirm_reset")]
        ]
    )
    return keyboard
