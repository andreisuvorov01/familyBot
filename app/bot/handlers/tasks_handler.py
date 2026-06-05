from aiogram import Router, types, F
from aiogram.filters import Command
from app.bot.keyboards import get_main_inline_keyboard
from app.core.models.user import User, UserRole, TaskCreationMode
from app.core.models.Task import TaskVisibility
from app.core.repositories.task_repository import TaskRepository
from app.bot.services.task_service import TaskParser

router = Router()

RESERVED_MENU_TEXTS = {"📋 Список дел", "📊 Статистика", "⚙️ Настройки"}


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

    title, visibility, deadline, error = TaskParser.parse_message(normalized_text)
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
        deadline=deadline
    )

    vis_text = "🔒 Личная" if visibility != TaskVisibility.COMMON else "👥 Семейная"
    deadline_text = f"\n⏰ Дедлайн: {deadline.strftime('%d.%m %H:%M')}" if deadline else ""

    await message.answer(
        f"✅ <b>Задача создана!</b>\n\n"
        f"📌 {title}\n"
        f"📂 {vis_text}{deadline_text}"
    )
