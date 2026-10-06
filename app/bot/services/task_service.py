import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from app.core.models.Task import TaskVisibility, TaskPriority
from app.core.timeutils import get_tz, to_naive_utc


class TaskParser:
    @staticmethod
    def parse_message(
        text: str, tz_name: Optional[str] = None
    ) -> Tuple[str, TaskVisibility, Optional[datetime], Optional[TaskPriority], Optional[str]]:
        """
        Парсит сообщение задачи.
        Пример: 'л Купить молоко завтра в 15:00'
        Возвращает: (title, visibility, deadline, priority, error)
        """
        visibility = TaskVisibility.COMMON
        title = text
        deadline = None
        priority = None

        # Часовой пояс пользователя (по умолчанию — Москва)
        user_tz = get_tz(tz_name)
        # Работаем с наивным локальным временем и локализуем в конце (корректно при переходе на летнее время)
        now_local = datetime.now(user_tz).replace(tzinfo=None)

        # 1. Определяем видимость
        if text.lower().startswith('л '):
            visibility = TaskVisibility.WIFE # Будет уточнено в хендлере в зависимости от роли
            title = text[2:].strip()
        elif text.lower().startswith('с '):
            visibility = TaskVisibility.COMMON
            title = text[2:].strip()

        # 2. Определяем приоритет (!, !!, !!!)
        if '!!!' in title:
            priority = TaskPriority.HIGH
            title = title.replace('!!!', '').strip()
        elif '!!' in title:
            priority = TaskPriority.MEDIUM
            title = title.replace('!!', '').strip()
        elif '!' in title:
            priority = TaskPriority.LOW
            title = title.replace('!', '').strip()

        # 3. Простой парсинг времени (очень базовый)
        deadline_local = None

        if 'сегодня' in title.lower():
            deadline_local = now_local.replace(hour=23, minute=59, second=0, microsecond=0)
            title = re.sub(r'\bсегодня\b', '', title, flags=re.IGNORECASE).strip()
        elif 'завтра' in title.lower():
            deadline_local = (now_local + timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
            title = re.sub(r'\bзавтра\b', '', title, flags=re.IGNORECASE).strip()

        # Поиск времени HH:MM
        time_match = re.search(r'(\d{1,2}):(\d{2})', title)
        if time_match:
            hours, minutes = map(int, time_match.groups())
            if 0 <= hours < 24 and 0 <= minutes < 60:
                if not deadline_local:
                    deadline_local = now_local
                deadline_local = deadline_local.replace(hour=hours, minute=minutes, second=0, microsecond=0)
                title = title.replace(time_match.group(0), '').strip()

        # Очистка от двойных пробелов и служебных слов рядом со временем.
        title = re.sub(r'\bв\s*$', '', title, flags=re.IGNORECASE).strip()
        title = re.sub(r'\s+', ' ', title).strip()

        if deadline_local:
            # Конвертируем локальное время в UTC и делаем его наивным для БД
            deadline = to_naive_utc(user_tz.localize(deadline_local))

        if not title:
            return title, visibility, deadline, priority, "Не удалось создать задачу: текст задачи пустой."

        return title, visibility, deadline, priority, None
