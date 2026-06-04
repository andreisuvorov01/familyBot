from aiogram import BaseMiddleware, types
from typing import Dict, Any, Callable, Awaitable
from app.core.database import async_session_maker
from app.core.repositories.user_repository import UserRepository

class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)

class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        session = data["session"]
        user_repo = UserRepository(session)
        db_user = await user_repo.get_by_tg_id(user.id)

        data["db_user"] = db_user
        data["user_repo"] = user_repo

        return await handler(event, data)
