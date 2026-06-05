import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from app.core.models.Task import TaskVisibility

class TaskParser:
    @staticmethod
    def parse_message(text: str) -> Tuple[str, TaskVisibility, Optional[datetime], Optional[str]]:
        """
        Парсит сообщение задачи.
        Пример: 'л Купить молоко завтра в 15:00'
        Возвращает: (title, visibility, deadline, error)
        """
        visibility = TaskVisibility.COMMON
        title = text
        deadline = None

        # 1. Определяем видимость
        if text.lower().startswith('л '):
            visibility = TaskVisibility.WIFE # Будет уточнено в хендлере в зависимости от роли
            title = text[2:].strip()
        elif text.lower().startswith('с '):
            visibility = TaskVisibility.COMMON
            title = text[2:].strip()

        # 2. Простой парсинг времени (очень базовый)
        now = datetime.utcnow()

        if 'сегодня' in title.lower():
            deadline = now.replace(hour=23, minute=59)
            title = re.sub(r'\bсегодня\b', '', title, flags=re.IGNORECASE).strip()
        elif 'завтра' in title.lower():
            deadline = (now + timedelta(days=1)).replace(hour=23, minute=59)
            title = re.sub(r'\bзавтра\b', '', title, flags=re.IGNORECASE).strip()

        # Поиск времени HH:MM
        time_match = re.search(r'(\d{1,2}):(\d{2})', title)
        if time_match:
            hours, minutes = map(int, time_match.groups())
            if 0 <= hours < 24 and 0 <= minutes < 60:
                if not deadline:
                    deadline = now
                deadline = deadline.replace(hour=hours, minute=minutes)
                title = title.replace(time_match.group(0), '').strip()

        # Очистка от двойных пробелов и служебных слов рядом со временем.
        title = re.sub(r'\bв\s*$', '', title, flags=re.IGNORECASE).strip()
        title = re.sub(r'\s+', ' ', title).strip()

        if not title:
            return title, visibility, deadline, "Не удалось создать задачу: текст задачи пустой."

        return title, visibility, deadline, None
