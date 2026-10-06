"""Работа со временем. В БД все даты — наивный UTC, пользователю показываем в его поясе."""
from datetime import datetime, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from app.core.models.user import DEFAULT_TIMEZONE

REPEAT_STEPS = {
    "daily": relativedelta(days=1),
    "weekly": relativedelta(weeks=1),
    "monthly": relativedelta(months=1),
}


def get_tz(name: str | None) -> pytz.BaseTzInfo:
    try:
        return pytz.timezone(name or DEFAULT_TIMEZONE)
    except pytz.UnknownTimeZoneError:
        return pytz.timezone(DEFAULT_TIMEZONE)


def is_valid_timezone(name: str) -> bool:
    return name in pytz.all_timezones_set


def utcnow() -> datetime:
    """Текущее время как наивный UTC (формат хранения в БД)."""
    return datetime.utcnow()


def to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(pytz.UTC).replace(tzinfo=None)


def to_local(value: datetime, tz_name: str | None) -> datetime:
    """Наивный UTC -> aware-время в поясе пользователя."""
    aware = pytz.UTC.localize(value) if value.tzinfo is None else value
    return aware.astimezone(get_tz(tz_name))


def format_local(value: datetime, tz_name: str | None, fmt: str = "%d.%m в %H:%M") -> str:
    return to_local(value, tz_name).strftime(fmt)


def next_occurrence(deadline: datetime, repeat_rule: str, tz_name: str | None, now: datetime | None = None) -> datetime:
    """Следующий дедлайн повторяющейся задачи (наивный UTC), строго в будущем.

    Шаг считается в поясе пользователя (чтобы «каждый месяц в 10:00» оставалось 10:00)
    календарными месяцами, а не 30 днями. Пропущенные повторы перескакиваются.
    """
    step = REPEAT_STEPS.get(repeat_rule, REPEAT_STEPS["daily"])
    now = now or utcnow()
    tz = get_tz(tz_name)
    base_local = to_local(deadline, tz_name).replace(tzinfo=None)

    n = 1
    while True:
        candidate_local = tz.localize(base_local + step * n)
        candidate = to_naive_utc(candidate_local)
        if candidate > now:
            return candidate
        n += 1
        if n > 10000:  # защита от бесконечного цикла
            return now + timedelta(days=1)
