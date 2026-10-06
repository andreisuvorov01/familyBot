"""Синхронизация с Google Calendar на фейковом Calendar API."""
import itertools

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import async_session_maker
from app.core.models.google import CalendarSyncJob, GoogleAccount, TaskCalendarEvent
from app.core.models.Task import Task
from app.services import calendar_sync
from app.services import google_calendar as gc
from app.services.crypto import encrypt

from .conftest import auth

pytestmark = pytest.mark.asyncio


class FakeCalendar:
    """События в памяти: {calendar_id: {event_id: event}}"""

    def __init__(self):
        self.calendars: dict[str, dict[str, dict]] = {}
        self._ids = itertools.count(1)
        self.revoked = False

    def api(self, *_):
        fake = self

        class Api:
            async def insert_event(self, cal, body):
                eid = f"ev{next(fake._ids)}"
                event = {**body, "id": eid, "etag": f"e-{eid}-1", "status": "confirmed"}
                fake.calendars.setdefault(cal, {})[eid] = event
                return event

            async def patch_event(self, cal, eid, body):
                event = fake.calendars.get(cal, {}).get(eid)
                if not event or event["status"] == "cancelled":
                    raise gc.EventNotFound(404, "not found")
                event.update(body, etag=f"e-{eid}-{next(fake._ids)}")
                return event

            async def delete_event(self, cal, eid):
                event = fake.calendars.get(cal, {}).get(eid)
                if event:
                    event["status"] = "cancelled"

            async def list_changes(self, cal, sync_token):
                items = list(fake.calendars.get(cal, {}).values()) if sync_token else []
                return items, "token"

        return Api()


@pytest.fixture
def fake_google(monkeypatch):
    fake = FakeCalendar()
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "secret")

    async def refresh(token):
        if token == "revoked":
            raise gc.GoogleAuthError("invalid_grant")
        return "access"

    monkeypatch.setattr(gc, "refresh_access_token", refresh)
    monkeypatch.setattr(gc, "CalendarApi", fake.api)
    return fake


async def connect(user_id: int, calendar_id: str, token: str = "refresh"):
    async with async_session_maker() as s:
        s.add(GoogleAccount(user_id=user_id, refresh_token_enc=encrypt(token), calendar_id=calendar_id, enabled=True, sync_token="t0"))
        await s.commit()


async def create(client, tg_id, **body):
    body.setdefault("title", "Задача")
    body.setdefault("deadline", "2030-05-01T10:00:00Z")
    resp = await client.post("/api/tasks/", json=body, headers=auth(tg_id))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def count(model) -> int:
    async with async_session_maker() as s:
        return await s.scalar(select(func.count()).select_from(model))


async def test_no_jobs_without_connected_accounts(client, family, fake_google):
    await create(client, 101)
    assert await count(CalendarSyncJob) == 0


async def test_common_task_goes_to_both_calendars(client, family, fake_google):
    await connect(1, "cal-h")
    await connect(2, "cal-w")
    task = await create(client, 101, title="Купить молоко", priority="high")
    await calendar_sync.process_sync_jobs()

    for cal in ("cal-h", "cal-w"):
        (event,) = fake_google.calendars[cal].values()
        assert event["summary"] == "Купить молоко"
        assert event["colorId"] == "11"
        assert event["end"]["dateTime"] == "2030-05-01T10:00:00Z"
        assert event["extendedProperties"]["private"]["familybot_task_id"] == str(task["id"])
    assert fake_google.calendars["cal-w"][next(iter(fake_google.calendars["cal-w"]))]["start"]["timeZone"] == "Asia/Yekaterinburg"
    assert await count(CalendarSyncJob) == 0


async def test_private_task_only_in_owner_calendar_and_removed_when_made_private(client, family, fake_google):
    await connect(1, "cal-h")
    await connect(2, "cal-w")
    await create(client, 101, title="Личная", visibility="private")
    shared = await create(client, 101, title="Общая")
    await calendar_sync.process_sync_jobs()
    assert len(fake_google.calendars["cal-h"]) == 2
    assert len(fake_google.calendars["cal-w"]) == 1

    await client.patch(f"/api/tasks/{shared['id']}", json={"visibility": "private"}, headers=auth(101))
    await calendar_sync.process_sync_jobs()
    assert [e["status"] for e in fake_google.calendars["cal-w"].values()] == ["cancelled"]


async def test_done_and_delete_propagate(client, family, fake_google):
    await connect(1, "cal-h")
    task = await create(client, 101, title="Сделать")
    await calendar_sync.process_sync_jobs()

    await client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth(101))
    await calendar_sync.process_sync_jobs()
    (event,) = fake_google.calendars["cal-h"].values()
    assert event["summary"] == "✅ Сделать" and event["colorId"] == "8"

    await client.delete(f"/api/tasks/{task['id']}", headers=auth(101))
    await calendar_sync.process_sync_jobs()
    assert event["status"] == "cancelled"
    assert await count(TaskCalendarEvent) == 0


async def test_pull_moves_deadline_and_propagates(client, family, fake_google):
    await connect(1, "cal-h")
    await connect(2, "cal-w")
    task = await create(client, 101, title="Встреча")
    await calendar_sync.process_sync_jobs()

    # Пользователь перенёс событие в своём Google Календаре
    (event,) = fake_google.calendars["cal-h"].values()
    event.update(
        start={"dateTime": "2030-05-02T14:30:00Z"},
        end={"dateTime": "2030-05-02T15:00:00Z"},
        summary="Встреча с врачом",
        etag="changed-by-user",
        updated="2099-01-01T00:00:00Z",
    )
    await calendar_sync.pull_calendar_changes()

    async with async_session_maker() as s:
        db_task = await s.get(Task, task["id"])
        assert db_task.title == "Встреча с врачом"
        assert db_task.deadline.isoformat() == "2030-05-02T15:00:00"

    await calendar_sync.process_sync_jobs()
    (partner_event,) = fake_google.calendars["cal-w"].values()
    assert partner_event["summary"] == "Встреча с врачом"
    assert partner_event["end"]["dateTime"] == "2030-05-02T15:00:00Z"

    # Наши собственные изменения при следующем опросе не применяются повторно
    await calendar_sync.pull_calendar_changes()
    assert await count(CalendarSyncJob) == 0


async def test_event_deleted_in_google_only_unlinks(client, family, fake_google):
    await connect(1, "cal-h")
    await create(client, 101)
    await calendar_sync.process_sync_jobs()
    (event,) = fake_google.calendars["cal-h"].values()
    event.update(status="cancelled", etag="deleted")
    await calendar_sync.pull_calendar_changes()
    assert await count(TaskCalendarEvent) == 0
    assert await count(Task) == 1


async def test_revoked_token_disables_account_and_notifies(client, family, fake_google, clean_tables):
    await connect(1, "cal-h", token="revoked")
    await create(client, 101)
    clean_tables.reset_mock()
    await calendar_sync.process_sync_jobs()
    async with async_session_maker() as s:
        account = await s.get(GoogleAccount, 1)
        assert account.enabled is False and account.last_error
    assert clean_tables.await_args.args[0] == 101


async def test_status_and_disconnect(client, family, fake_google, monkeypatch):
    revoked = []

    async def fake_revoke(token):
        revoked.append(token)

    monkeypatch.setattr(gc, "revoke_token", fake_revoke)
    status = (await client.get("/api/google/status", headers=auth(101))).json()
    assert status == {"available": True, "connected": False, "enabled": False, "email": None, "last_error": None, "last_synced_at": None}

    url = (await client.post("/api/google/auth-url", headers=auth(101))).json()["url"]
    assert url.startswith("https://accounts.google.com/") and "calendar.app.created" in url and "state=" in url

    await connect(1, "cal-h")
    assert (await client.get("/api/google/status", headers=auth(101))).json()["connected"] is True
    assert (await client.delete("/api/google", headers=auth(101))).status_code == 200
    assert revoked == ["refresh"]
    assert (await client.get("/api/google/status", headers=auth(101))).json()["connected"] is False


async def test_oauth_callback(client, family, fake_google, monkeypatch):
    from app.api.google import make_state
    from app.core.models.user import User

    async def fake_exchange(code):
        assert code == "the-code"
        return {"access_token": "a", "refresh_token": "r", "id_token": None}

    class OAuthApi:
        def __init__(self, *_):
            pass

        async def calendar_exists(self, cal):
            return False

        async def create_calendar(self, summary, tz):
            assert summary == "FamilyBot" and tz == "Europe/Moscow"
            return "new-cal"

    monkeypatch.setattr(gc, "exchange_code", fake_exchange)
    monkeypatch.setattr(gc, "CalendarApi", OAuthApi)
    await create(client, 101)

    async with async_session_maker() as s:
        state = make_state(await s.get(User, 1))
    resp = await client.get("/api/google/callback", params={"state": state, "code": "the-code"})
    assert resp.status_code == 200 and "подключён" in resp.text

    async with async_session_maker() as s:
        account = await s.get(GoogleAccount, 1)
        assert account.calendar_id == "new-cal" and account.enabled
    assert await count(CalendarSyncJob) == 1  # выгрузка существующих задач

    bad = await client.get("/api/google/callback", params={"state": "forged", "code": "x"})
    assert bad.status_code == 400
