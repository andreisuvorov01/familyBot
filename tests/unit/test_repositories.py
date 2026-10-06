from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.Task import Task, TaskVisibility
from app.core.models.user import User, UserRole
from app.core.repositories.task_repository import TaskRepository
from app.core.repositories.user_repository import UserRepository


class TestUserRepository:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def user_repo(self, mock_session):
        return UserRepository(mock_session)

    @pytest.mark.asyncio
    async def test_get_by_tg_id_found(self, user_repo, mock_session):
        # Arrange
        mock_user = User(id=1, tg_id=123, username="test")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result

        # Act
        result = await user_repo.get_by_tg_id(123)

        # Assert
        assert result == mock_user
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_tg_id_not_found(self, user_repo, mock_session):
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Act
        result = await user_repo.get_by_tg_id(999)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_create_user(self, user_repo, mock_session):
        # Act
        user = await user_repo.create(123, "test_user")

        # Assert
        assert user.tg_id == 123
        assert user.username == "test_user"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()


class TestTaskRepository:
    @pytest.fixture
    def mock_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def task_repo(self, mock_session):
        return TaskRepository(mock_session)

    @pytest.mark.asyncio
    async def test_get_family_tasks(self, task_repo, mock_session):
        # Arrange
        mock_tasks = [Task(id=1, title="Test"), Task(id=2, title="Test2")]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_tasks
        mock_session.execute.return_value = mock_result

        # Act
        user = User(id=1, family_id="FAM123", role=UserRole.HUSBAND)
        tasks = await task_repo.get_family_tasks(user)

        # Assert
        assert len(tasks) == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_visibility_filter_uses_owner(self, task_repo, mock_session):
        """Личные задачи фильтруются по owner_id, а не по роли."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await task_repo.get_family_tasks(User(id=7, family_id="FAM123", role=UserRole.WIFE))

        stmt = mock_session.execute.call_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "tasks.owner_id = 7" in compiled
        assert "WIFE" not in compiled

    @pytest.mark.asyncio
    async def test_add_task_flushes_without_commit(self, task_repo, mock_session):
        task = Task(title="Test Task", owner_id=1, family_id="FAM123", visibility=TaskVisibility.COMMON)

        result = await task_repo.add(task)

        assert result is task
        mock_session.add.assert_called_once_with(task)
        mock_session.flush.assert_called_once()
        mock_session.commit.assert_not_called()
