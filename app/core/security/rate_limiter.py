import time
from typing import Dict, Tuple, Optional
from collections import defaultdict
from fastapi import HTTPException, Request
import os

# Попытка подключить Redis для распределённого rate limiting
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class InMemoryRateLimiter:
    """In-memory rate limiter (только для single-worker / разработки)"""

    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.limits = {
            "api": (60, 100),    # 100 запросов в минуту
            "auth": (300, 10),   # 10 попыток за 5 минут
            "bot": (60, 30),     # 30 сообщений в минуту
        }

    def is_rate_limited(self, key: str, limit_type: str = "api") -> Tuple[bool, int]:
        if limit_type not in self.limits:
            return False, 0

        window, max_requests = self.limits[limit_type]
        current_time = time.time()

        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if current_time - req_time < window
        ]

        if len(self.requests[key]) >= max_requests:
            retry_after = int(window - (current_time - self.requests[key][0]))
            return True, retry_after

        self.requests[key].append(current_time)
        return False, 0


_redis_client: Optional[object] = None


async def get_redis():
    """Ленивое подключение к Redis"""
    global _redis_client
    if _redis_client is None and REDIS_AVAILABLE:
        redis_url = os.getenv("REDIS_URL")
        enable_redis = os.getenv("ENABLE_REDIS", "false").lower() == "true"
        if redis_url and enable_redis:
            try:
                _redis_client = aioredis.from_url(redis_url, decode_responses=True)
                await _redis_client.ping()
            except Exception:
                _redis_client = None
    return _redis_client


# Fallback: in-memory лимитер
_in_memory_limiter = InMemoryRateLimiter()


async def is_rate_limited_redis(redis, key: str, window: int, max_req: int) -> Tuple[bool, int]:
    """Распределённый rate limiting через Redis (sliding window)"""
    try:
        now = time.time()
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window)
        results = await pipe.execute()
        count = results[1]
        if count >= max_req:
            oldest = await redis.zrange(key, 0, 0, withscores=True)
            retry_after = int(window - (now - oldest[0][1])) if oldest else window
            return True, retry_after
        return False, 0
    except Exception:
        return False, 0


rate_limiter = _in_memory_limiter


async def rate_limit_middleware(request: Request, call_next):
    """Middleware для rate limiting (Redis если доступен, иначе in-memory)"""
    client_ip = request.client.host if request.client else "unknown"

    # Пропускаем health check и статику
    if request.url.path in ("/health", "/") or request.url.path.startswith("/static"):
        return await call_next(request)

    rate_key = f"ratelimit:api:{client_ip}"
    window, max_req = 60, 100

    redis = await get_redis()
    if redis:
        is_limited, retry_after = await is_rate_limited_redis(redis, rate_key, window, max_req)
    else:
        is_limited, retry_after = _in_memory_limiter.is_rate_limited(client_ip, "api")

    if is_limited:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "retry_after": retry_after,
                "message": f"Please try again in {retry_after} seconds"
            }
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(max_req)
    return response


def check_auth_rate_limit(tg_id: int) -> bool:
    key = f"auth:{tg_id}"
    is_limited, _ = _in_memory_limiter.is_rate_limited(key, "auth")
    return not is_limited


def check_bot_rate_limit(tg_id: int) -> bool:
    key = f"bot:{tg_id}"
    is_limited, _ = _in_memory_limiter.is_rate_limited(key, "bot")
    return not is_limited
