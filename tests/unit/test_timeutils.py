from datetime import datetime

from app.core.timeutils import format_local, next_occurrence, to_naive_utc


def test_monthly_keeps_local_time_and_month_end():
    # 31 января 10:00 МСК = 07:00 UTC -> 28 февраля 10:00 МСК
    nxt = next_occurrence(datetime(2030, 1, 31, 7, 0), "monthly", "Europe/Moscow", now=datetime(2030, 1, 31, 8, 0))
    assert nxt == datetime(2030, 2, 28, 7, 0)


def test_weekly_skips_missed_occurrences():
    nxt = next_occurrence(datetime(2030, 1, 1, 9, 0), "weekly", "UTC", now=datetime(2030, 1, 20, 0, 0))
    assert nxt == datetime(2030, 1, 22, 9, 0)


def test_daily_respects_dst():
    # Берлин: 30 марта 2030 — переход на летнее время. 09:00 локального остаётся 09:00
    before = datetime(2030, 3, 30, 8, 0)  # 09:00 CET
    nxt = next_occurrence(before, "daily", "Europe/Berlin", now=before)
    assert nxt == datetime(2030, 3, 31, 7, 0)  # 09:00 CEST
    assert format_local(nxt, "Europe/Berlin", "%H:%M") == "09:00"


def test_unknown_timezone_falls_back_to_default():
    assert format_local(datetime(2030, 1, 1, 12, 0), "Mars/Base", "%H:%M") == "15:00"


def test_to_naive_utc():
    from datetime import timedelta, timezone

    aware = datetime(2030, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=3)))
    assert to_naive_utc(aware) == datetime(2030, 1, 1, 9, 0)
