from datetime import datetime, time, timedelta
from typing import Dict, List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from app.core.database import async_session_maker
from app.core.logging_config import log_with_context, logger
from app.core.models.Task import Task, TaskPriority, TaskVisibility
from app.core.models.user import User
from app.core.repositories.task_repository import TaskRepository
from app.core.repositories.user_repository import UserRepository
from app.core.timeutils import format_local, to_local, utcnow
from app.services.notifications import h, open_app_button, open_task_button, send_safe

MORNING_HOUR = 9
# Задание запускается каждые 15 минут; сводку получает тот, у кого сейчас 09:00–09:14
MORNING_WINDOW_MINUTES = 15
PRIORITY_ORDER = {TaskPriority.HIGH: 0, TaskPriority.MEDIUM: 1, TaskPriority.LOW: 2, None: 3}
PRIORITY_MARK = {TaskPriority.HIGH: "🔥 ", TaskPriority.MEDIUM: "⚡ "}


def _is_morning(now_utc: datetime, tz_name: str) -> bool:
    local = to_local(now_utc, tz_name)
    return local.hour == MORNING_HOUR and local.minute < MORNING_WINDOW_MINUTES


def build_morning_summary(tasks: List[Task], tz_name: str, now_utc: datetime) -> str | None:
    """Сводка: просроченные и сегодняшние задачи + важные без даты. None — сводка не нужна."""
    local_today = to_local(now_utc, tz_name).date()
    end_of_day = datetime.combine(local_today, time.max)

    overdue, today, important = [], [], []
    for t in tasks:
        if t.deadline:
            local_deadline = to_local(t.deadline, tz_name).replace(tzinfo=None)
            if t.deadline < now_utc:
                overdue.append(t)
            elif local_deadline <= end_of_day:
                today.append(t)
        elif t.priority == TaskPriority.HIGH:
            important.append(t)

    if not (overdue or today or important):
        return None

    def key(t: Task):
        return PRIORITY_ORDER.get(t.priority, 3), t.deadline or datetime.max

    def line(t: Task, with_time: bool) -> str:
        suffix = f" — {format_local(t.deadline, tz_name, '%H:%M')}" if with_time and t.deadline else ""
        return f"• {PRIORITY_MARK.get(t.priority, '')}{h(t.title)}{suffix}"

    parts = ["☕ <b>Доброе утро!</b>"]
    if overdue:
        parts.append("\n🔥 <b>Просрочено:</b>")
        parts += [line(t, False) for t in sorted(overdue, key=key)[:5]]
    if today:
        parts.append("\n📋 <b>На сегодня:</b>")
        parts += [line(t, True) for t in sorted(today, key=lambda t: t.deadline)[:7]]
    if important:
        parts.append("\n⭐ <b>Важное без даты:</b>")
        parts += [line(t, False) for t in important[:3]]
    rest = len(tasks) - len(overdue) - len(today) - len(important)
    if rest > 0:
        parts.append(f"\n<i>И ещё {rest} в списке</i>")
    return "\n".join(parts)


async def send_morning_notifications():
    """Утренняя сводка в 09:00 по часовому поясу каждого пользователя"""
    now = utcnow()
    async with async_session_maker() as session:
        task_repo = TaskRepository(session)
        stmt = select(User).where(User.family_id.is_not(None), User.morning_summary_enabled.is_(True))
        users = [u for u in (await session.execute(stmt)).scalars().all() if _is_morning(now, u.timezone)]

        sent = 0
        for user in users:
            try:
                # Только видимые пользователю задачи — без личных задач партнёра
                tasks = await task_repo.get_pending_visible_tasks(user)
                message = build_morning_summary(tasks, user.timezone, now)
                if message:
                    markup = InlineKeyboardMarkup(inline_keyboard=[[open_app_button()]])
                    if await send_safe(user.tg_id, message, markup):
                        sent += 1
            except Exception as e:  # noqa: BLE001
                log_with_context("ERROR", f"Failed to send morning notification: {e}", user_id=user.id)

        if users:
            logger.info(f"Morning notifications: {sent} sent of {len(users)} users")


async def check_deadlines():
    """Напоминания о дедлайнах (за 30 минут и о просрочке)"""
    async with async_session_maker() as session:
        user_repo = UserRepository(session)
        task_repo = TaskRepository(session)

        now = utcnow()
        tasks = await task_repo.get_pending_tasks_with_deadlines(now + timedelta(minutes=30))
        if not tasks:
            return

        tasks_by_owner: Dict[int, List[Task]] = {}
        for task in tasks:
            tasks_by_owner.setdefault(task.owner_id, []).append(task)

        owners = (await session.execute(select(User).where(User.id.in_(tasks_by_owner)))).scalars().all()
        user_map = {u.id: u for u in owners}

        sent = errors = 0
        for owner_id, owner_tasks in tasks_by_owner.items():
            user = user_map.get(owner_id)
            if not user:
                continue
            try:
                expired = [t for t in owner_tasks if t.deadline < now]
                upcoming = [t for t in owner_tasks if t.deadline >= now]

                if user.notifications_enabled:
                    if expired:
                        sent += await send_expired_notification(user, expired)
                    if upcoming:
                        sent += await send_upcoming_notification(user, upcoming)

                common_expired = [t for t in expired if t.visibility == TaskVisibility.COMMON]
                common_upcoming = [t for t in upcoming if t.visibility == TaskVisibility.COMMON]
                if common_expired or common_upcoming:
                    for partner in await user_repo.get_partners(user):
                        if not partner.notifications_enabled:
                            continue
                        if common_expired:
                            sent += await send_expired_notification(partner, common_expired, is_partner=True)
                        if common_upcoming:
                            sent += await send_upcoming_notification(partner, common_upcoming, is_partner=True)
            except Exception as e:  # noqa: BLE001
                errors += 1
                log_with_context("ERROR", f"Failed to process deadline notifications: {e}", user_id=user.id)

            # Помечаем даже при выключенных уведомлениях — иначе после включения придёт лавина
            for task in owner_tasks:
                task.reminder_sent = True

        await session.commit()
        logger.info(f"Deadline check: {len(tasks)} tasks, {sent} notifications sent, {errors} errors")


def _task_buttons(tasks: List[Task], with_complete: bool) -> InlineKeyboardMarkup:
    rows = []
    for task in tasks[:5]:
        row = []
        if with_complete:
            row.append(InlineKeyboardButton(text=f"✅ {task.title[:20]}", callback_data=f"complete_task_{task.id}"))
        row.append(open_task_button(task.id, "📱" if with_complete else f"📱 {task.title[:20]}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _task_list(tasks: List[Task]) -> str:
    text = "\n".join(f"• {h(t.title)}" for t in tasks[:5])
    if len(tasks) > 5:
        text += f"\n• ...и еще {len(tasks) - 5}"
    return text


async def send_expired_notification(user: User, tasks: List[Task], is_partner: bool = False) -> int:
    """Уведомление о просроченных задачах"""
    if not tasks:
        return 0
    prefix = "🔔 <b>Партнер пропустил дедлайн!</b>\n" if is_partner else "🔥 <b>Дедлайн пропущен!</b>\n"
    if len(tasks) == 1:
        message = f"{prefix}Задача: {h(tasks[0].title)}"
    else:
        message = f"{prefix}Просроченные задачи:\n{_task_list(tasks)}"
    return int(await send_safe(user.tg_id, message, _task_buttons(tasks, with_complete=not is_partner)))


async def send_upcoming_notification(user: User, tasks: List[Task], is_partner: bool = False) -> int:
    """Уведомление о приближающихся дедлайнах"""
    if not tasks:
        return 0
    prefix = "🔔 <b>У партнера скоро дедлайн!</b>\n" if is_partner else "⏰ <b>Скоро дедлайн!</b>\n"
    if len(tasks) == 1:
        task = tasks[0]
        minutes_left = max(0, int((task.deadline - utcnow()).total_seconds() / 60))
        message = (
            f"{prefix}Задача: {h(task.title)}\n"
            f"Срок: {format_local(task.deadline, user.timezone, '%H:%M')} (через {minutes_left} мин)"
        )
    else:
        message = f"{prefix}Скоро дедлайн у задач:\n{_task_list(tasks)}\nОсталось меньше 30 минут"
    return int(await send_safe(user.tg_id, message, _task_buttons(tasks, with_complete=not is_partner)))
