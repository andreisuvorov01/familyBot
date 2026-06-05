import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
from app.core.models.schemas import (
    TaskCreate, TaskUpdate, SubtaskCreate, SubtaskUpdate, UserSettingsUpdate,
    TaskVisibilityEnum, RepeatRuleEnum, TaskStatusEnum
)


class TestTaskCreateSchema:
    def test_valid_task_create(self):
        """Тест создания валидной задачи"""
        task_data = {
            "title": "Test Task",
            "description": "Test description",
            "visibility": TaskVisibilityEnum.COMMON,
            "deadline": datetime.utcnow() + timedelta(days=1),
            "repeat_rule": RepeatRuleEnum.DAILY
        }
        
        task = TaskCreate(**task_data)
        
        assert task.title == "Test Task"
        assert task.visibility == TaskVisibilityEnum.COMMON
        assert task.repeat_rule == RepeatRuleEnum.DAILY
    
    def test_task_create_without_optional_fields(self):
        """Тест создания задачи без опциональных полей"""
        task_data = {
            "title": "Test Task"
        }
        
        task = TaskCreate(**task_data)
        
        assert task.title == "Test Task"
        assert task.description is None
        assert task.visibility == TaskVisibilityEnum.COMMON
        assert task.deadline is None
        assert task.repeat_rule is None
    
    def test_task_create_invalid_title(self):
        """Тест с невалидным заголовком"""
        task_data = {
            "title": "",  # Пустой заголовок
        }
        
        with pytest.raises(ValidationError) as exc_info:
            TaskCreate(**task_data)
        
        assert "title" in str(exc_info.value)
    
    def test_task_create_past_deadline(self):
        """Тест с прошедшим дедлайном"""
        task_data = {
            "title": "Test Task",
            "deadline": datetime.utcnow() - timedelta(days=1)
        }
        
        with pytest.raises(ValidationError) as exc_info:
            TaskCreate(**task_data)
        
        assert "Deadline cannot be in the past" in str(exc_info.value)
    
    def test_task_create_long_description(self):
        """Тест с слишком длинным описанием"""
        task_data = {
            "title": "Test Task",
            "description": "A" * 1025  # Превышает лимит в 1024 символа
        }
        
        with pytest.raises(ValidationError) as exc_info:
            TaskCreate(**task_data)
        
        assert "description" in str(exc_info.value)


class TestTaskUpdateSchema:
    def test_valid_task_update(self):
        """Тест валидного обновления задачи"""
        update_data = {
            "title": "Updated Task",
            "status": TaskStatusEnum.DONE,
            "visibility": TaskVisibilityEnum.PRIVATE
        }
        
        task_update = TaskUpdate(**update_data)
        
        assert task_update.title == "Updated Task"
        assert task_update.status == TaskStatusEnum.DONE
        assert task_update.visibility == TaskVisibilityEnum.PRIVATE
    
    def test_partial_update(self):
        """Тест частичного обновления"""
        update_data = {
            "status": TaskStatusEnum.DONE
        }
        
        task_update = TaskUpdate(**update_data)
        
        assert task_update.status == TaskStatusEnum.DONE
        assert task_update.title is None
        assert task_update.description is None
    
    def test_update_with_future_deadline(self):
        """Тест обновления с будущим дедлайном"""
        update_data = {
            "title": "Updated Task",
            "deadline": datetime.utcnow() + timedelta(days=2)
        }
        
        task_update = TaskUpdate(**update_data)
        
        assert task_update.deadline > datetime.utcnow()


class TestSubtaskCreateSchema:
    def test_valid_subtask_create(self):
        """Тест создания валидной подзадачи"""
        subtask_data = {
            "title": "Test Subtask"
        }
        
        subtask = SubtaskCreate(**subtask_data)
        
        assert subtask.title == "Test Subtask"
    
    def test_subtask_create_empty_title(self):
        """Тест с пустым заголовком подзадачи"""
        subtask_data = {
            "title": ""
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SubtaskCreate(**subtask_data)
        
        assert "title" in str(exc_info.value)
    
    def test_subtask_create_long_title(self):
        """Тест с слишком длинным заголовком подзадачи"""
        subtask_data = {
            "title": "A" * 256  # Превышает лимит в 255 символов
        }
        
        with pytest.raises(ValidationError) as exc_info:
            SubtaskCreate(**subtask_data)
        
        assert "title" in str(exc_info.value)


class TestEnums:
    def test_task_visibility_enum(self):
        """Тест enum видимости задач"""
        assert TaskVisibilityEnum.PRIVATE.value == "private"
        assert TaskVisibilityEnum.COMMON.value == "common"
        
        # Проверка валидных значений
        assert TaskVisibilityEnum("private") == TaskVisibilityEnum.PRIVATE
        assert TaskVisibilityEnum("common") == TaskVisibilityEnum.COMMON
        
        # Проверка невалидного значения
        with pytest.raises(ValueError):
            TaskVisibilityEnum("invalid")
    
    def test_repeat_rule_enum(self):
        """Тест enum правил повторения"""
        assert RepeatRuleEnum.DAILY.value == "daily"
        assert RepeatRuleEnum.WEEKLY.value == "weekly"
        assert RepeatRuleEnum.MONTHLY.value == "monthly"
    
    def test_task_status_enum(self):
        """Тест enum статусов задач"""
        assert TaskStatusEnum.PENDING.value == "pending"
        assert TaskStatusEnum.DONE.value == "done"
        assert TaskStatusEnum.CANCELLED.value == "cancelled"


class TestSubtaskUpdateSchema:
    def test_valid_subtask_update(self):
        update = SubtaskUpdate(is_done=True)

        assert update.is_done is True


class TestUserSettingsUpdateSchema:
    def test_valid_user_settings_update(self):
        update = UserSettingsUpdate(notifications_enabled=False, task_creation_mode="message", role="wife")

        assert update.notifications_enabled is False
        assert update.task_creation_mode.value == "message"
        assert update.role.value == "wife"
