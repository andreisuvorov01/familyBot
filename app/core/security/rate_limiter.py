import os
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse

# Попытка подключить Redis для распределённого rate limiting
try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

LIMITS = {
    "api": (60, 100),  # 100 запросов в минуту с IP
    "auth_fail": (300, 10),  # 10 неудачных авторизаций за 5 минут с IP
    "bot": (60, 30),  # 30 сообщений в минуту
}


class InMemoryRateLimiter:
    """In-memory rate limiter (только для single-worker / разработки)"""

    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)

    def _prune(self, key: str, window: int) -> list:
        now = time.time()
        self.requests[key] = [t for t in self.requests[key] if now - t < window]
        return self.requests[key]

    def is_rate_limited(self, key: str, limit_type: str = "api", record: bool = True) -> Tuple[bool, int]:
        if limit_type not in LIMITS:
            return False, 0
        window, max_requests = LIMITS[limit_type]
        hits = self._prune(key, window)
        if len(hits) >= max_requests:
            return True, int(window - (time.time() - hits[0]))
        if record:
            hits.append(time.time())
        return False, 0

    def record(self, key: str, limit_type: str) -> None:
        window, _ = LIMITS[limit_type]
        self._prune(key, window).append(time.time())


_redis_client: Optional[object] = None
_redis_checked = False


async def get_redis():
    """Ленивое подключение к Redis (если задан REDIS_URL и ENABLE_REDIS=true)"""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    if REDIS_AVAILABLE:
        redis_url = os.getenv("REDIS_URL")
        enable_redis = os.getenv("ENABLE_REDIS", "false").lower() == "true"
        if redis_url and enable_redis:
            try:
                client = aioredis.from_url(redis_url, decode_responses=True)
                await client.ping()
                _redis_client = client
            except Exception:
                _redis_client = None
    return _redis_client


_in_memory_limiter = InMemoryRateLimiter()
rate_limiter = _in_memory_limiter


async def _redis_hit(redis, key: str, window: int, max_req: int, record: bool = True) -> Tuple[bool, int]:
    """Sliding window в Redis"""
    try:
        now = time.time()
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zcard(key)
        if record:
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


async def check_limit(key: str, limit_type: str, record: bool = True) -> Tuple[bool, int]:
    window, max_req = LIMITS[limit_type]
    redis = await get_redis()
    if redis:
        return await _redis_hit(redis, f"ratelimit:{limit_type}:{key}", window, max_req, record)
    return _in_memory_limiter.is_rate_limited(f"{limit_type}:{key}", limit_type, record)


def client_ip(request: Request) -> str:
    # X-Forwarded-For выставляет Nginx
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_middleware(request: Request, call_next):
    """Middleware для rate limiting (Redis если доступен, иначе in-memory)"""
    if request.url.path in ("/health", "/") or request.url.path.startswith("/static"):
        return await call_next(request)

    is_limited, retry_after = await check_limit(client_ip(request), "api")
    if is_limited:
        # Исключение из middleware превращается в 500, поэтому отвечаем напрямую
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(LIMITS["api"][1])
    return response


async def is_auth_blocked(ip: str) -> bool:
    limited, _ = await check_limit(ip, "auth_fail", record=False)
    return limited


async def register_auth_failure(ip: str) -> None:
    redis = await get_redis()
    if redis:
        window, max_req = LIMITS["auth_fail"]
        await _redis_hit(redis, f"ratelimit:auth_fail:{ip}", window, max_req, record=True)
    else:
        _in_memory_limiter.record(f"auth_fail:{ip}", "auth_fail")


def check_bot_rate_limit(tg_id: int) -> bool:
    is_limited, _ = _in_memory_limiter.is_rate_limited(f"bot:{tg_id}", "bot")
    return not is_limited
