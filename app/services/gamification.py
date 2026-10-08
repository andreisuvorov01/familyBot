"""Геймификация: XP, уровни и достижения считаются из истории выполнений (task_completions).

Ничего не хранится отдельно — отмена и повторное выполнение не накручивают очки.
"""
from math import isqrt

XP_PER_TASK = 10
XP_PER_LEVEL_STEP = 50  # уровень N начинается с 50*(N-1)^2 XP

# (id, иконка, название, порог, метрика)
BADGES = [
    ("first", "🌱", "Первый шаг", 1, "total"),
    ("ten", "⭐", "10 задач", 10, "total"),
    ("fifty", "🏅", "50 задач", 50, "total"),
    ("hundred", "🏆", "100 задач", 100, "total"),
    ("streak3", "🔥", "3 дня подряд", 3, "streak"),
    ("streak7", "⚡", "Неделя подряд", 7, "streak"),
    ("streak30", "👑", "Месяц подряд", 30, "streak"),
]


def progress(done: int, streak_days: int) -> dict:
    xp = done * XP_PER_TASK
    level = isqrt(xp // XP_PER_LEVEL_STEP) + 1
    start, end = XP_PER_LEVEL_STEP * (level - 1) ** 2, XP_PER_LEVEL_STEP * level**2
    metrics = {"total": done, "streak": streak_days}
    return {
        "xp": xp,
        "level": level,
        "level_xp": xp - start,
        "level_xp_needed": end - start,
        "badges": [
            {"id": id_, "icon": icon, "title": title, "earned": metrics[metric] >= need}
            for id_, icon, title, need, metric in BADGES
        ],
    }
