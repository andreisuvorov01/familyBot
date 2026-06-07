from aiogram import Router, types, F
from aiogram.filters import Command
from app.bot.keyboards import get_main_inline_keyboard
from app.core.models.user import User, UserRole, TaskCreationMode
from app.core.models.Task import TaskVisibility
from app.core.repositories.task_repository import TaskRepository
from app.bot.services.task_service import TaskParser
import pytz

router = Router()

RESERVED_MENU_TEXTS = {"📋 Список дел", "📊 Статистика", "⚙️ Настройки"}

HELP_TEXT = (
    "<b>Как пользоваться?</b>\n\n"
    "📝 <b>Создание задач</b>\n"
    "Вы можете создавать задачи через сообщения в чате бота. Используйте префиксы:\n"
    "• <b>л </b> — личная задача\n"
    "• <b>с </b> — общая семейная задача\n\n"
    "Пример: <code>с Купить молоко завтра в 15:00</code>\n\n"
    "⚙️ <b>Настройки</b>\n"
    "В меню настроек можно переключить режим создания задач:\n"
    "• <b>Команды</b> — создание только через кнопки или спец. команды.\n"
    "• <b>Сообщения</b> — каждое ваше текстовое сообщение боту станет новой задачей.\n\n"
    "🤝 <b>Семья</b>\n"
    "Семейные задачи видят оба партнера. При создании или выполнении общей задачи партнер получит уведомление."
)


@router.message(F.text == "📋 Список дел")
@router.message(Command("tasks"))
async def cmd_tasks(message: types.Message):
    await message.answer("Ваши задачи:", reply_markup=get_main_inline_keyboard())

@router.message(F.text == "📊 Статистика")
@router.message(Command("stats"))
async def cmd_stats(message: types.Message, db_user: User, session):
    if not db_user or not db_user.family_id:
        return

    task_repo = TaskRepository(session)
    tasks = await task_repo.get_family_tasks(db_user.family_id, db_user.role)

    if not tasks:
        await message.answer("📊 У вас пока нет задач.")
        return

    total = len(tasks)
    done = len([t for t in tasks if t.status == "done"])
    pending = total - done

    await message.answer(
        f"📊 <b>Статистика семьи</b>\n\n"
        f"• Всего задач: {total}\n"
        f"• Выполнено: {done}\n"
        f"• В работе: {pending}\n"
        f"• Процент: {(done/total*100):.1f}%"
    )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

@router.callback_query(F.data == "help")
async def help_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(HELP_TEXT, parse_mode="HTML", reply_markup=get_main_inline_keyboard())

@router.callback_query(F.data == "stats")
async def stats_callback(callback: types.CallbackQuery, db_user: User, session):
    task_repo = TaskRepository(session)
    tasks = await task_repo.get_family_tasks(db_user.family_id, db_user.role)

    total = len(tasks)
    done = len([t for t in tasks if t.status == "done"])

    await callback.message.edit_text(
        f"📊 <b>Статистика семьи</b>\n\n"
        f"• Всего задач: {total}\n"
        f"• Выполнено: {done}\n"
        f"• В работе: {total - done}\n",
        reply_markup=get_main_inline_keyboard()
    )

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

    title, visibility, deadline, priority, error = TaskParser.parse_message(normalized_text)
    if error:
        await message.answer(f"❌ {error}")
        return

    if visibility == TaskVisibility.WIFE:  # В парсере 'л ' ставит WIFE как заглушку.
        visibility = TaskVisibility.HUSBAND if db_user.role == UserRole.HUSBAND else TaskVisibility.WIFE

    task_repo = TaskRepository(session)
    await task_repo.create_task(
        title=title,
        owner_id=db_user.id,
        family_id=db_user.family_id,
        visibility=visibility,
        priority=priority,
        deadline=deadline
    )

    vis_text = "🔒 Личная" if visibility != TaskVisibility.COMMON else "👥 Семейная"

    deadline_text = ""
    if deadline:
        # Конвертируем наивный UTC в Московское время
        if deadline.tzinfo is None:
            deadline_utc = pytz.UTC.localize(deadline)
        else:
            deadline_utc = deadline.astimezone(pytz.UTC)

        deadline_msk = deadline_utc.astimezone(pytz.timezone('Europe/Moscow'))
        deadline_text = f"\n⏰ Дедлайн: {deadline_msk.strftime('%d.%m %H:%M')}"

    priority_text = ""
    if priority:
        p_map = {"low": "Малый", "medium": "Средний", "high": "Высокий"}
        priority_text = f"\n🎯 Приоритет: {p_map.get(priority.value, priority.value)}"

    await message.answer(
        f"✅ <b>Задача создана!</b>\n\n"
        f"📌 {title}\n"
        f"📂 {vis_text}{priority_text}{deadline_text}"
    )


@router.callback_query(F.data.startswith("complete_task_"))
async def complete_task_callback(callback: types.CallbackQuery, db_user: User, session):
    if not db_user:
        return

    try:
        task_id = int(callback.data.replace("complete_task_", ""))
        task_repo = TaskRepository(session)

        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        from app.core.models.Task import Task, TaskVisibility

        visibilities = [TaskVisibility.COMMON]
        if db_user.role == UserRole.HUSBAND:
            visibilities.append(TaskVisibility.HUSBAND)
        else:
            visibilities.append(TaskVisibility.WIFE)

        stmt = (
            select(Task)
            .where(
                Task.id == task_id,
                Task.family_id == db_user.family_id,
                Task.visibility.in_(visibilities)
            )
            .options(selectinload(Task.subtasks))
        )
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()

        if not task:
            await callback.answer("Задача не найдена или у вас нет к ней доступа", show_alert=True)
            return

        if task.status == "done":
            await callback.answer("Задача уже выполнена")
            return

        # Обновляем статус задачи
        update_data = {"status": "done"}

        # Если задача цикличная, обрабатываем перенос (логика совпадает с API)
        if task.repeat_rule:
            from datetime import timedelta
            update_data["status"] = "pending"
            update_data["reminder_sent"] = False

            if task.deadline:
                delta_map = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1), "monthly": timedelta(days=30)}
                delta = delta_map.get(task.repeat_rule, timedelta(days=1))
                update_data["deadline"] = task.deadline + delta
                for subtask in task.subtasks:
                    subtask.is_done = False

        await task_repo.update_task(task_id, db_user.family_id, **update_data)

        # Редактируем сообщение уведомления
        new_text = callback.message.text
        if "🔥 <b>Дедлайн пропущен!</b>" in callback.message.html_text:
            new_text = f"✅ <b>Выполнено!</b> (Дедлайн был пропущен)\n<s>{task.title}</s>"
        elif "⏰ <b>Скоро дедлайн!</b>" in callback.message.html_text:
            new_text = f"✅ <b>Выполнено!</b>\n<s>{task.title}</s>"
        else:
            # Универсальный вариант
            new_text = f"✅ <b>Выполнено:</b> {task.title}"

        await callback.message.edit_text(new_text, parse_mode="HTML", reply_markup=None)
        await callback.answer("Задача отмечена выполненной!")

    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
