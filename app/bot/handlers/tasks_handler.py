from aiogram import F, Router, types
from aiogram.filters import Command

from app.bot.keyboards import get_main_inline_keyboard
from app.bot.services.task_service import TaskParser
from app.core.models.Task import TaskVisibility
from app.core.models.user import TaskCreationMode, User
from app.core.timeutils import format_local
from app.services.notifications import h, task_keyboard
from app.services.task_service import TaskError, TaskService

router = Router()

RESERVED_MENU_TEXTS = {"📋 Список дел", "📊 Статистика", "⚙️ Настройки"}

HELP_TEXT = (
    "<b>Как пользоваться?</b>\n\n"
    "📝 <b>Создание задач</b>\n"
    "Вы можете создавать задачи через сообщения в чате бота. Используйте префиксы:\n"
    "• <b>л </b> — личная задача\n"
    "• <b>с </b> — общая семейная задача\n\n"
    "Пример: <code>с Купить молоко завтра в 15:00</code>\n"
    "Приоритет: <code>!</code> — низкий, <code>!!</code> — средний, <code>!!!</code> — высокий.\n\n"
    "⚙️ <b>Настройки</b>\n"
    "В меню настроек можно переключить режим создания задач:\n"
    "• <b>Команды</b> — создание только через кнопки или спец. команды.\n"
    "• <b>Сообщения</b> — каждое ваше текстовое сообщение боту станет новой задачей.\n\n"
    "🤝 <b>Семья</b>\n"
    "Семейные задачи видят оба партнера. При создании или выполнении общей задачи партнер получит уведомление.\n\n"
    "📅 <b>Google Календарь</b>\n"
    "Подключается в настройках Mini App — задачи с дедлайном появятся в календаре «FamilyBot»."
)


async def _stats_text(db_user: User, session) -> str:
    stats = await TaskService(session).get_stats(db_user)
    if not stats["total"]:
        return "📊 У вас пока нет задач."
    percent = stats["done"] / stats["total"] * 100
    lines = [
        "📊 <b>Статистика семьи</b>\n",
        f"• Всего задач: {stats['total']}",
        f"• Выполнено: {stats['done']}",
        f"• В работе: {stats['pending']}",
        f"• Просрочено: {stats['overdue']}",
        f"• Процент: {percent:.1f}%",
        f"• За неделю выполнено: {stats['done_this_week']}",
    ]
    if stats["streak_days"]:
        lines.append(f"• 🔥 Серия: {stats['streak_days']} дн.")
    for m in stats["members"]:
        lines.append(f"  — {h(m['name'])}: {m['done_week']} за неделю")
    return "\n".join(lines)


@router.message(F.text == "📋 Список дел")
@router.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    await message.answer("Ваши задачи:", reply_markup=get_main_inline_keyboard())


@router.message(F.text == "📊 Статистика")
@router.message(Command("stats"))
async def cmd_stats(message: types.Message, db_user: User, session):
    if not db_user or not db_user.family_id:
        return
    await message.answer(await _stats_text(db_user, session))


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=get_main_inline_keyboard())


@router.callback_query(F.data == "help")
async def help_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(HELP_TEXT, parse_mode="HTML", reply_markup=get_main_inline_keyboard())


@router.callback_query(F.data == "stats")
async def stats_callback(callback: types.CallbackQuery, db_user: User, session):
    if not db_user or not db_user.family_id:
        await callback.answer()
        return
    await callback.message.edit_text(await _stats_text(db_user, session), reply_markup=get_main_inline_keyboard())


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: types.Message, db_user: User, session):
    if not db_user or not db_user.family_id or not message.text:
        return

    normalized_text = message.text.strip()
    if normalized_text in RESERVED_MENU_TEXTS:
        if normalized_text == "⚙️ Настройки":
            # Настройки обрабатываются отдельным роутером. Защита нужна на случай,
            # если catch-all роутер задач зарегистрирован раньше.
            return
        if normalized_text == "📋 Список дел":
            await message.answer("Ваши задачи:", reply_markup=get_main_inline_keyboard())
            return
        if normalized_text == "📊 Статистика":
            await cmd_stats(message, db_user, session)
            return

    # Проверяем режим или наличие явного префикса: "л " — личная, "с " — семейная.
    is_prefix = normalized_text.lower().startswith(('л ', 'с '))
    if db_user.task_creation_mode != TaskCreationMode.MESSAGE and not is_prefix:
        return

    title, visibility, deadline, priority, error = TaskParser.parse_message(normalized_text, db_user.timezone)
    if error:
        await message.answer(f"❌ {error}")
        return

    is_private = visibility != TaskVisibility.COMMON
    task = await TaskService(session).create_task(
        db_user,
        title=title,
        private=is_private,
        priority=priority,
        deadline=deadline,
    )

    vis_text = "🔒 Личная" if is_private else "👥 Семейная"
    deadline_text = f"\n⏰ Дедлайн: {format_local(deadline, db_user.timezone, '%d.%m %H:%M')}" if deadline else ""
    priority_text = ""
    if priority:
        p_map = {"low": "Низкий", "medium": "Средний", "high": "Высокий"}
        priority_text = f"\n🎯 Приоритет: {p_map.get(priority.value, priority.value)}"

    await message.answer(
        f"✅ <b>Задача создана!</b>\n\n"
        f"📌 {h(title)}\n"
        f"📂 {vis_text}{priority_text}{deadline_text}",
        reply_markup=task_keyboard(task.id),
    )


@router.callback_query(F.data.startswith("complete_task_"))
async def complete_task_callback(callback: types.CallbackQuery, db_user: User, session):
    if not db_user:
        return

    try:
        task_id = int(callback.data.replace("complete_task_", ""))
    except ValueError:
        await callback.answer("Некорректная задача", show_alert=True)
        return

    try:
        task, change = await TaskService(session).complete_task(db_user, task_id)
    except TaskError:
        await callback.answer("Задача не найдена или у вас нет к ней доступа", show_alert=True)
        return

    if change.kind == "none":
        await callback.answer("Задача уже выполнена")
        return

    # В сводном уведомлении несколько задач — убираем только нажатую кнопку
    markup = callback.message.reply_markup
    other_rows = [
        row for row in (markup.inline_keyboard if markup else [])
        if not any(b.callback_data == callback.data for b in row)
    ]
    if any(b.callback_data and b.callback_data.startswith("complete_task_") for row in other_rows for b in row):
        await callback.message.edit_reply_markup(reply_markup=types.InlineKeyboardMarkup(inline_keyboard=other_rows))
        await callback.answer(f"✅ {task.title[:150]}")
        return

    html_text = callback.message.html_text or ""
    if change.kind == "rescheduled":
        new_text = f"🔄 <b>Выполнено!</b> Следующий раз: {format_local(task.deadline, db_user.timezone)}\n{h(task.title)}" \
            if task.deadline else f"🔄 <b>Выполнено!</b>\n{h(task.title)}"
    elif "Дедлайн пропущен" in html_text:
        new_text = f"✅ <b>Выполнено!</b> (Дедлайн был пропущен)\n<s>{h(task.title)}</s>"
    else:
        new_text = f"✅ <b>Выполнено!</b>\n<s>{h(task.title)}</s>"

    await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
    await callback.answer("Задача отмечена выполненной!")
