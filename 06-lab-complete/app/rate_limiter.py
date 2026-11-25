"""
Rate limiting (tiêu chí 7) — Sliding window 60s lưu trên Redis sorted set.
"""
import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60
_fallback_windows: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str) -> dict:
    """
    Kiểm tra rate limit cho mỗi API key (sliding window 60s).
    Vượt RATE_LIMIT_PER_MINUTE → HTTP 429 kèm header Retry-After.
    """
    limit = settings.rate_limit_per_minute
    now = time.time()
    window_start = now - WINDOW_SECONDS
    redis_key = f"ratelimit:{key}"

    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            _, current_count = pipe.execute()

            if current_count >= limit:
                oldest = r.zrange(redis_key, 0, 0, withscores=True)
                retry_after = (
                    max(1, int(oldest[0][1] + WINDOW_SECONDS - now) + 1)
                    if oldest
                    else WINDOW_SECONDS
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "limit": limit,
                        "window_seconds": WINDOW_SECONDS,
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            member = f"{now}:{uuid.uuid4().hex}"
            pipe = r.pipeline()
            pipe.zadd(redis_key, {member: now})
            pipe.expire(redis_key, WINDOW_SECONDS)
            pipe.execute()

            return {
                "limit": limit,
                "remaining": max(0, limit - current_count - 1),
            }
        except HTTPException:
            raise
        except Exception:
            pass

    # Fallback in-memory chỉ khi Redis không khả dụng
    dq = _fallback_windows[key]
    while dq and dq[0] < window_start:
        dq.popleft()

    if len(dq) >= limit:
        retry_after = max(1, int(dq[0] + WINDOW_SECONDS - now) + 1)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": limit,
                "window_seconds": WINDOW_SECONDS,
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    dq.append(now)
    return {"limit": limit, "remaining": max(0, limit - len(dq))}
