from datetime import datetime

from app.core.models.Task import Task, TaskPriority
from app.services.scheduler import _is_morning, build_morning_summary


def task(title, deadline=None, priority=None):
    return Task(title=title, deadline=deadline, priority=priority, status="pending")


def test_morning_window_uses_user_timezone():
    now = datetime(2030, 1, 1, 6, 5)  # 09:05 МСК, 11:05 Екатеринбург
    assert _is_morning(now, "Europe/Moscow")
    assert not _is_morning(now, "Asia/Yekaterinburg")


def test_summary_groups_overdue_today_and_escapes():
    now = datetime(2030, 1, 1, 6, 0)  # 09:00 МСК
    tasks = [
        task("<старое>", datetime(2029, 12, 31, 10, 0)),
        task("Сегодня вечером", datetime(2030, 1, 1, 17, 0)),
        task("Завтра", datetime(2030, 1, 2, 10, 0)),
        task("Важное", priority=TaskPriority.HIGH),
        task("Без даты"),
    ]
    text = build_morning_summary(tasks, "Europe/Moscow", now)
    assert "Просрочено" in text and "&lt;старое&gt;" in text
    assert "Сегодня вечером — 20:00" in text
    assert "Важное" in text
    assert "Завтра" not in text
    assert "И ещё 2" in text


def test_no_summary_when_nothing_relevant():
    now = datetime(2030, 1, 1, 6, 0)
    assert build_morning_summary([task("Когда-нибудь")], "Europe/Moscow", now) is None
