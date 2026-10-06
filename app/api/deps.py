from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security import verify_telegram_data
from app.core.database import get_async_session
from app.core.logging_config import log_with_context
from app.core.models.user import User
from app.core.repositories.user_repository import UserRepository
from app.core.security.rate_limiter import client_ip, is_auth_blocked, register_auth_failure


async def get_current_user(
    request: Request,
    init_data: str = Header(..., alias="X-TG-Data"),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Пользователь Mini App по подписанным initData.

    Лимит считает только НЕУДАЧНЫЕ попытки по IP: раньше лимит «10 за 5 минут»
    применялся к каждому успешному запросу, и активная работа в Mini App давала 429.
    """
    ip = client_ip(request)
    if await is_auth_blocked(ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many authentication attempts")

    try:
        user_data = verify_telegram_data(init_data)
    except HTTPException:
        await register_auth_failure(ip)
        raise

    user = await UserRepository(session).get_by_tg_id(user_data["id"])
    if not user or not user.family_id:
        log_with_context("WARNING", "Access denied: user not found or no family", user_id=user_data.get("id"))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return user
