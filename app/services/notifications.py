"""Отправка сообщений в Telegram: экранирование, проверка настроек, кнопка «Открыть»."""
from html import escape
from typing import Callable, Iterable, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.bot.instance import bot
from app.core.config import settings
from app.core.logging_config import log_with_context
from app.core.models.user import User


def h(value: object) -> str:
    """Экранирование пользовательского текста для parse_mode=HTML."""
    return escape(str(value or ""), quote=False)


def display_name(user: User) -> str:
    return f"@{user.username}" if user.username else "Партнёр"


def webapp_task_url(task_id: int) -> str:
    sep = "&" if "?" in settings.WEBAPP_URL else "?"
    return f"{settings.WEBAPP_URL}{sep}task={task_id}"


def open_app_button(text: str = "📱 Открыть задачи") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=settings.WEBAPP_URL))


def open_task_button(task_id: int, text: str = "📱 Открыть") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=webapp_task_url(task_id)))


def task_keyboard(task_id: int, with_complete: bool = False) -> InlineKeyboardMarkup:
    row = []
    if with_complete:
        row.append(InlineKeyboardButton(text="✅ Выполнено", callback_data=f"complete_task_{task_id}"))
    row.append(open_task_button(task_id))
    return InlineKeyboardMarkup(inline_keyboard=[row])


async def send_safe(tg_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
    try:
        await bot.send_message(tg_id, text, parse_mode="HTML", reply_markup=reply_markup)
        return True
    except Exception as e:  # noqa: BLE001 — пользователь мог заблокировать бота
        log_with_context("WARNING", f"Failed to send message: {e}", tg_id=tg_id)
        return False


async def notify_users(
    recipients: Iterable[User],
    build_text: Callable[[User], str],
    task_id: Optional[int] = None,
) -> int:
    """Уведомить пользователей, у которых включены уведомления. Текст строится под получателя
    (например, дедлайн в его часовом поясе)."""
    sent = 0
    for user in recipients:
        if not user.notifications_enabled:
            continue
        markup = task_keyboard(task_id) if task_id else None
        if await send_safe(user.tg_id, build_text(user), markup):
            sent += 1
    return sent
