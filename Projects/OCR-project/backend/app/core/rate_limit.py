from __future__ import annotations
import time
import redis as redis_lib
from fastapi import HTTPException, Request

from app.config import settings

_redis: redis_lib.Redis | None = None


def get_redis() -> redis_lib.Redis:
    global _redis
    if _redis is None:
        _redis = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def check_rate_limit(user_id: str, limit: int, window_seconds: int = 60) -> None:
    r = get_redis()
    bucket = int(time.time() // window_seconds)
    key = f"ratelimit:{user_id}:{bucket}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, window_seconds * 2)
    if count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
