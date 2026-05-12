import time
from typing import Dict, Tuple
from collections import defaultdict
from fastapi import HTTPException, Request
from app.core.config import settings


class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.limits = {
            "api": (60, 100),  # 100 запросов в минуту
            "auth": (300, 10),  # 10 попыток за 5 минут
            "bot": (60, 30),   # 30 сообщений в минуту
        }

    def is_rate_limited(self, key: str, limit_type: str = "api") -> Tuple[bool, int]:
        """Проверяет, превышен ли лимит запросов"""
        if limit_type not in self.limits:
            return False, 0

        window, max_requests = self.limits[limit_type]
        current_time = time.time()

        # Очищаем старые запросы
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if current_time - req_time < window
        ]

        # Проверяем лимит
        if len(self.requests[key]) >= max_requests:
            retry_after = int(window - (current_time - self.requests[key][0]))
            return True, retry_after

        # Добавляем новый запрос
        self.requests[key].append(current_time)
        return False, 0


rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """Middleware для rate limiting"""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Создаем ключ для rate limiting
    rate_key = f"{client_ip}:{user_agent}"
    
    # Проверяем rate limit
    is_limited, retry_after = rate_limiter.is_rate_limited(rate_key, "api")
    
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": retry_after,
                "message": f"Please try again in {retry_after} seconds"
            }
        )
    
    # Добавляем заголовки с информацией о rate limit
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = str(
        100 - len(rate_limiter.requests[rate_key])
    )
    
    return response


def check_auth_rate_limit(tg_id: int) -> bool:
    """Проверка rate limit для аутентификации"""
    key = f"auth:{tg_id}"
    is_limited, _ = rate_limiter.is_rate_limited(key, "auth")
    return not is_limited


def check_bot_rate_limit(tg_id: int) -> bool:
    """Проверка rate limit для бота"""
    key = f"bot:{tg_id}"
    is_limited, _ = rate_limiter.is_rate_limited(key, "bot")
    return not is_limited