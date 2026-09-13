import time
from typing import Any, cast

from fastapi import Request
from redis.asyncio import Redis

from app.db.models import APIKey


async def enforce_rate_limit(request: Request, key: APIKey, redis: Redis) -> None:
    minute = int(time.time() // 60)
    minute_key = f"crawlforge:rate:{key.id}:{minute}"
    month = time.strftime("%Y-%m")
    month_key = f"crawlforge:quota:{key.id}:{month}"
    script = """
    local minute_count = redis.call('INCR', KEYS[1])
    redis.call('EXPIRE', KEYS[1], 120)
    local month_count = redis.call('INCR', KEYS[2])
    redis.call('EXPIRE', KEYS[2], 3024000)
    return {minute_count, month_count}
    """
    values = cast(list[Any], await cast(Any, redis.eval(script, 2, minute_key, month_key)))
    minute_count, month_count = int(values[0]), int(values[1])
    request.state.rate_limit = (
        key.rate_limit_rpm,
        max(0, key.rate_limit_rpm - minute_count),
        (minute + 1) * 60,
    )
    if minute_count > key.rate_limit_rpm:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=429,
            detail={"code": "RATE_LIMITED", "message": "request rate exceeded"},
            headers={"Retry-After": str(max(1, (minute + 1) * 60 - int(time.time())))},
        )
    if month_count > key.monthly_quota:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=429, detail={"code": "QUOTA_EXCEEDED", "message": "monthly quota exceeded"}
        )
