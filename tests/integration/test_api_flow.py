from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.database import async_session_maker
from app.core.models.Task import Task, TaskCompletion

from .conftest import auth

pytestmark = pytest.mark.asyncio


async def create(client, tg_id, **body):
    body.setdefault("title", "Задача")
    resp = await client.post("/api/tasks/", json=body, headers=auth(tg_id))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_private_tasks_visible_only_to_owner(client, family):
    await create(client, 101, title="Общая")
    await create(client, 101, title="Личная мужа", visibility="private")
    await create(client, 202, title="Личная жены", visibility="private")

    husband = {t["title"] for t in (await client.get("/api/tasks/", headers=auth(101))).json()}
    wife = {t["title"] for t in (await client.get("/api/tasks/", headers=auth(202))).json()}
    assert husband == {"Общая", "Личная мужа"}
    assert wife == {"Общая", "Личная жены"}


async def test_private_not_leaked_when_roles_match(client, family):
    """Раньше личные задачи определялись ролью: при одинаковой роли партнёр их видел."""
    await client.patch("/api/tasks/profile", json={"role": "husband"}, headers=auth(202))
    await create(client, 101, title="Секрет", visibility="private")
    titles = {t["title"] for t in (await client.get("/api/tasks/", headers=auth(202))).json()}
    assert "Секрет" not in titles


async def test_only_owner_can_make_task_private(client, family):
    task = await create(client, 101, title="Общая")
    resp = await client.patch(f"/api/tasks/{task['id']}", json={"visibility": "private"}, headers=auth(202))
    assert resp.status_code == 403
    resp = await client.patch(f"/api/tasks/{task['id']}", json={"visibility": "private"}, headers=auth(101))
    assert resp.status_code == 200 and resp.json()["visibility"] == "husband"


async def test_deadline_with_timezone_is_stored_as_utc(client, family):
    task = await create(client, 101, deadline="2030-01-10T12:00:00+03:00")
    assert task["deadline"].startswith("2030-01-10T09:00:00")


async def test_monthly_repeat_uses_calendar_months_and_records_history(client, family):
    task = await create(client, 101, title="Оплатить", deadline="2030-01-31T07:00:00Z", repeat_rule="monthly")
    resp = await client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth(101))
    body = resp.json()
    assert body["status"] == "pending"
    assert body["deadline"].startswith("2030-02-28T07:00:00")  # не 2 марта, как при +30 дней

    async with async_session_maker() as s:
        count = await s.scalar(select(func.count()).select_from(TaskCompletion))
    assert count == 1


async def test_overdue_repeat_moves_to_future(client, family):
    past = (datetime.utcnow() - timedelta(days=10)).replace(microsecond=0).isoformat() + "Z"
    task = await create(client, 101, deadline=past, repeat_rule="daily")
    body = (await client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth(101))).json()
    assert datetime.fromisoformat(body["deadline"].replace("Z", "+00:00")).replace(tzinfo=None) > datetime.utcnow()


async def test_done_and_reopen(client, family):
    task = await create(client, 101)
    body = (await client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=auth(202))).json()
    assert body["status"] == "done" and body["completed_by_id"] == 2 and body["completed_at"]
    body = (await client.patch(f"/api/tasks/{task['id']}", json={"status": "pending"}, headers=auth(202))).json()
    assert body["status"] == "pending" and body["completed_at"] is None


async def test_partner_notification_is_escaped_and_respects_settings(client, family, clean_tables):
    sent = clean_tables
    await create(client, 101, title="<b>молоко</b> & хлеб")
    assert sent.await_count == 1
    assert sent.await_args.args[0] == 202
    assert "&lt;b&gt;молоко&lt;/b&gt; &amp; хлеб" in sent.await_args.args[1]

    await client.patch("/api/tasks/profile", json={"notifications_enabled": False}, headers=auth(202))
    await create(client, 101, title="Ещё")
    assert sent.await_count == 1


async def test_stats(client, family):
    a = await create(client, 101)
    await create(client, 101)
    await client.patch(f"/api/tasks/{a['id']}", json={"status": "done"}, headers=auth(202))
    stats = (await client.get("/api/tasks/stats", headers=auth(101))).json()
    assert stats["total"] == 2 and stats["done"] == 1 and stats["done_this_week"] == 1
    assert stats["streak_days"] == 1
    assert {m["name"]: m["done_week"] for m in stats["members"]} == {"Вы": 0, "@wife": 1}
    wife = next(m for m in stats["members"] if not m["is_me"])
    assert wife["xp"] == 10 and wife["level"] == 1
    assert [b["id"] for b in wife["badges"] if b["earned"]] == ["first"]


async def test_profile_timezone_validation(client, family):
    ok = await client.patch("/api/tasks/profile", json={"timezone": "Asia/Tokyo"}, headers=auth(101))
    assert ok.status_code == 200 and ok.json()["timezone"] == "Asia/Tokyo"
    bad = await client.patch("/api/tasks/profile", json={"timezone": "Mars/Base"}, headers=auth(101))
    assert bad.status_code == 422


async def test_many_requests_do_not_hit_auth_limit(client, family):
    """Раньше лимит «10 авторизаций за 5 минут» срабатывал на обычных запросах Mini App."""
    for _ in range(15):
        assert (await client.get("/api/tasks/", headers=auth(101))).status_code == 200


async def test_invalid_signature_rejected(client, family):
    resp = await client.get(
        "/api/tasks/", headers={"X-TG-Data": "user=%7B%22id%22%3A101%7D&auth_date=9999999999&hash=bad"}
    )
    assert resp.status_code == 403


async def test_subtasks_and_delete(client, family):
    task = await create(client, 101)
    sub = (await client.post(f"/api/tasks/{task['id']}/subtasks", json={"title": "Пункт"}, headers=auth(101))).json()
    assert (
        await client.patch(f"/api/tasks/subtasks/{sub['id']}", json={"is_done": True}, headers=auth(202))
    ).status_code == 200
    assert (await client.delete(f"/api/tasks/subtasks/{sub['id']}", headers=auth(101))).status_code == 200
    assert (await client.delete(f"/api/tasks/{task['id']}", headers=auth(202))).status_code == 200
    async with async_session_maker() as s:
        assert await s.scalar(select(func.count()).select_from(Task)) == 0


async def test_delete_profile(client, family):
    await create(client, 101, title="Моя")
    await create(client, 202, title="Жены")
    assert (await client.delete("/api/tasks/profile", headers=auth(101))).status_code == 200
    titles = {t["title"] for t in (await client.get("/api/tasks/", headers=auth(202))).json()}
    assert titles == {"Жены"}
