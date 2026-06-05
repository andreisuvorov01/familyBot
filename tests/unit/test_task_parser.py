from app.bot.services.task_service import TaskParser
from app.core.models.Task import TaskVisibility
import pytz


def test_parse_prefixed_private_task_with_deadline():
    title, visibility, deadline, error = TaskParser.parse_message("л Купить молоко завтра в 15:30")

    assert error is None
    assert title == "Купить молоко"
    assert visibility == TaskVisibility.WIFE
    assert deadline is not None

    # Конвертируем обратно в Московское время для проверки
    deadline_utc = pytz.UTC.localize(deadline)
    deadline_msk = deadline_utc.astimezone(pytz.timezone('Europe/Moscow'))
    assert deadline_msk.hour == 15
    assert deadline_msk.minute == 30


def test_parse_empty_task_returns_error():
    title, visibility, deadline, error = TaskParser.parse_message("л завтра 10:00")

    assert title == ""
    assert visibility == TaskVisibility.WIFE
    assert deadline is not None
    assert error == "Не удалось создать задачу: текст задачи пустой."
