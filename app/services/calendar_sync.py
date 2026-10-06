"""Синхронизация задач с Google Calendar.

Направление «бот → Google» — через outbox (таблица calendar_sync_jobs): задания пишутся
в той же транзакции, что и изменение задачи, и разбираются планировщиком бота
(process_sync_jobs) с повторными попытками. Направление «Google → бот» — периодический
опрос изменений по syncToken (pull_calendar_changes).
"""
from datetime import datetime, time, timedelta
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.logging_config import log_with_context, logger
from app.core.models.google import CalendarSyncJob, GoogleAccount, TaskCalendarEvent
from app.core.models.Task import Task, TaskVisibility
from app.core.models.user import User
from app.core.repositories.task_repository import visible_to
from app.core.timeutils import get_tz, to_naive_utc, utcnow
from app.services import google_calendar as gc
from app.services.crypto import decrypt
from app.services.notifications import send_safe

MAX_ATTEMPTS = 8
BATCH_SIZE = 50
RECONNECT_MESSAGE = "Доступ к Google Календарю отозван — подключите его заново в настройках Mini App."


# --- Постановка в очередь (вызывается из TaskService, без commit) ---

async def family_has_google(session: AsyncSession, family_id: str) -> bool:
    if not settings.google_enabled:
        return False
    stmt = (
        select(GoogleAccount.user_id)
        .join(User, User.id == GoogleAccount.user_id)
        .where(User.family_id == family_id, GoogleAccount.enabled.is_(True))
        .limit(1)
    )
    return (await session.execute(stmt)).first() is not None


async def enqueue_upsert(session: AsyncSession, task: Task) -> None:
    if await family_has_google(session, task.family_id):
        session.add(CalendarSyncJob(task_id=task.id, action="upsert", next_attempt_at=utcnow()))


async def enqueue_delete(session: AsyncSession, task: Task) -> None:
    """Вызывать ДО удаления задачи: связи с событиями удалятся каскадом."""
    links = (await session.execute(
        select(TaskCalendarEvent).where(TaskCalendarEvent.task_id == task.id)
    )).scalars().all()
    if links:
        payload = [{"user_id": link.user_id, "event_id": link.event_id} for link in links]
        session.add(CalendarSyncJob(task_id=task.id, action="delete", payload=payload, next_attempt_at=utcnow()))


async def enqueue_full_resync(session: AsyncSession, user: User) -> int:
    """После подключения календаря: выгрузить все видимые пользователю задачи с дедлайном."""
    stmt = select(Task.id).where(
        Task.family_id == user.family_id,
        visible_to(user),
        Task.deadline.is_not(None),
        Task.status != "cancelled",
    )
    task_ids = (await session.execute(stmt)).scalars().all()
    for task_id in task_ids:
        session.add(CalendarSyncJob(task_id=task_id, action="upsert", next_attempt_at=utcnow()))
    return len(task_ids)


# --- Обработка ---

class _SyncContext:
    """Кэш access token'ов на один прогон и обработка отозванного доступа."""

    def __init__(self, session: AsyncSession, http: httpx.AsyncClient):
        self.session = session
        self.http = http
        self._apis: dict[int, Optional[gc.CalendarApi]] = {}

    async def api_for(self, account: GoogleAccount) -> Optional[gc.CalendarApi]:
        if account.user_id in self._apis:
            return self._apis[account.user_id]
        api: Optional[gc.CalendarApi] = None
        try:
            token = await gc.refresh_access_token(decrypt(account.refresh_token_enc))
            api = gc.CalendarApi(token, self.http)
        except gc.GoogleAuthError:
            await self.disable_account(account)
        self._apis[account.user_id] = api
        return api

    async def disable_account(self, account: GoogleAccount) -> None:
        if not account.enabled:
            return
        account.enabled = False
        account.last_error = RECONNECT_MESSAGE
        user = await self.session.get(User, account.user_id)
        if user:
            await send_safe(user.tg_id, f"⚠️ {RECONNECT_MESSAGE}")
        log_with_context("WARNING", "Google account disabled: invalid grant", user_id=account.user_id)


async def _family_accounts(session: AsyncSession, family_id: str) -> dict[int, GoogleAccount]:
    stmt = (
        select(GoogleAccount)
        .join(User, User.id == GoogleAccount.user_id)
        .where(User.family_id == family_id, GoogleAccount.enabled.is_(True), GoogleAccount.calendar_id.is_not(None))
    )
    return {acc.user_id: acc for acc in (await session.execute(stmt)).scalars().all()}


async def _handle_upsert(ctx: _SyncContext, task_id: int) -> None:
    session = ctx.session
    task = await session.get(Task, task_id)
    if task is None:
        return  # задача удалена — события уберёт задание delete

    accounts = await _family_accounts(session, task.family_id)
    links = {
        link.user_id: link
        for link in (await session.execute(
            select(TaskCalendarEvent).where(TaskCalendarEvent.task_id == task.id)
        )).scalars().all()
    }
    targets = {task.owner_id} if task.visibility != TaskVisibility.COMMON else set(accounts)

    for user_id, account in accounts.items():
        link = links.get(user_id)
        user = await session.get(User, user_id)
        body = gc.build_event(task, user.timezone if user else settings.DEFAULT_TIMEZONE)
        api = await ctx.api_for(account)
        if api is None:
            continue

        if body is None or user_id not in targets:
            # Задача стала личной/без дедлайна/отменена — убираем событие
            if link:
                await api.delete_event(account.calendar_id, link.event_id)
                await session.delete(link)
            continue

        if link:
            try:
                event = await api.patch_event(account.calendar_id, link.event_id, body)
            except gc.EventNotFound:
                event = await api.insert_event(account.calendar_id, body)
                link.event_id = event["id"]
            link.etag = event.get("etag")
        else:
            event = await api.insert_event(account.calendar_id, body)
            session.add(TaskCalendarEvent(task_id=task.id, user_id=user_id, event_id=event["id"], etag=event.get("etag")))

    # Связи пользователей, у которых календарь отключён, просто забываем
    for user_id, link in links.items():
        if user_id not in accounts:
            await session.delete(link)


async def _handle_delete(ctx: _SyncContext, payload: list[dict]) -> None:
    for item in payload or []:
        account = await ctx.session.get(GoogleAccount, item["user_id"])
        if not account or not account.enabled or not account.calendar_id:
            continue
        api = await ctx.api_for(account)
        if api:
            await api.delete_event(account.calendar_id, item["event_id"])


async def process_sync_jobs() -> None:
    """Задание планировщика: отправить накопленные изменения в Google."""
    if not settings.google_enabled:
        return
    async with async_session_maker() as session, httpx.AsyncClient() as http:
        stmt = (
            select(CalendarSyncJob)
            .where(CalendarSyncJob.next_attempt_at <= utcnow())
            .order_by(CalendarSyncJob.id)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        jobs = (await session.execute(stmt)).scalars().all()
        if not jobs:
            return

        ctx = _SyncContext(session, http)
        done_upserts: set[int] = set()
        processed = failed = 0
        for job in jobs:
            try:
                async with session.begin_nested():
                    if job.action == "delete":
                        await _handle_delete(ctx, job.payload or [])
                    elif job.task_id not in done_upserts:  # дубликаты в одном прогоне схлопываем
                        await _handle_upsert(ctx, job.task_id)
                        done_upserts.add(job.task_id)
                await session.delete(job)
                processed += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                job.attempts += 1
                job.last_error = str(e)[:500]
                if job.attempts >= MAX_ATTEMPTS:
                    log_with_context("ERROR", f"Calendar sync job dropped: {e}", job_id=job.id, task_id=job.task_id)
                    await session.delete(job)
                else:
                    job.next_attempt_at = utcnow() + timedelta(minutes=min(2 ** job.attempts, 360))
        await session.commit()
        logger.info(f"Calendar sync: {processed} jobs processed, {failed} failed")


def _event_deadline(event: dict, tz_name: str) -> Optional[datetime]:
    end = event.get("end") or {}
    if end.get("dateTime"):
        return gc.parse_google_datetime(end["dateTime"])
    start = event.get("start") or {}
    if start.get("date"):  # событие на весь день -> 23:59 этого дня
        day = datetime.fromisoformat(start["date"]).date()
        return to_naive_utc(get_tz(tz_name).localize(datetime.combine(day, time(23, 59))))
    return None


async def _pull_account(ctx: _SyncContext, account: GoogleAccount) -> None:
    session = ctx.session
    api = await ctx.api_for(account)
    if api is None:
        return
    try:
        items, next_token = await api.list_changes(account.calendar_id, account.sync_token)
    except gc.SyncTokenExpired:
        account.sync_token = None
        return

    if account.sync_token:  # при первичной синхронизации только запоминаем токен
        user = await session.get(User, account.user_id)
        tz_name = user.timezone if user else settings.DEFAULT_TIMEZONE
        for event in items:
            await _apply_event(session, account, event, tz_name)

    account.sync_token = next_token
    account.last_synced_at = utcnow()


async def _apply_event(session: AsyncSession, account: GoogleAccount, event: dict, tz_name: str) -> None:
    link = (await session.execute(
        select(TaskCalendarEvent).where(
            TaskCalendarEvent.user_id == account.user_id,
            TaskCalendarEvent.event_id == event.get("id"),
        )
    )).scalar_one_or_none()
    if link is None or event.get("etag") == link.etag:
        return  # чужое событие или наше собственное изменение

    if event.get("status") == "cancelled":
        # Удаление в одном календаре не отменяет семейную задачу — просто отвязываем
        await session.delete(link)
        return

    task = await session.get(Task, link.task_id)
    link.etag = event.get("etag")
    if task is None:
        return

    updated = event.get("updated")
    if updated and task.updated_at and gc.parse_google_datetime(updated) <= task.updated_at:
        return  # в боте версия новее — last write wins

    changed = False
    new_deadline = _event_deadline(event, tz_name)
    if new_deadline and (task.deadline is None or abs((new_deadline - task.deadline).total_seconds()) > 60):
        task.deadline = new_deadline
        task.reminder_sent = False
        changed = True

    title = (event.get("summary") or "").removeprefix(gc.DONE_PREFIX).strip()[:255]
    if title and title != task.title:
        task.title = title
        changed = True

    if changed:
        task.updated_at = utcnow()
        await enqueue_upsert(session, task)  # разнести изменение в календари остальных
        log_with_context("INFO", "Task updated from Google Calendar", task_id=task.id, user_id=account.user_id)


async def pull_calendar_changes() -> None:
    """Задание планировщика: забрать изменения из Google (перенос/переименование/удаление событий)."""
    if not settings.google_enabled:
        return
    async with async_session_maker() as session, httpx.AsyncClient() as http:
        accounts = (await session.execute(
            select(GoogleAccount).where(GoogleAccount.enabled.is_(True), GoogleAccount.calendar_id.is_not(None))
        )).scalars().all()
        ctx = _SyncContext(session, http)
        for account in accounts:
            try:
                async with session.begin_nested():
                    await _pull_account(ctx, account)
            except Exception as e:  # noqa: BLE001
                account.last_error = str(e)[:500]
                log_with_context("ERROR", f"Calendar pull failed: {e}", user_id=account.user_id)
        await session.commit()
