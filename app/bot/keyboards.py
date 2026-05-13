from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
