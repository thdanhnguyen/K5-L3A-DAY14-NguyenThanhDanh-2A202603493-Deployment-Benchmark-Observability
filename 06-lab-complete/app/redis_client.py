"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

App vẫn khởi động được khi Redis chưa sẵn sàng (lazy connection, không ping lúc import).
"""
import redis

from app.config import settings


def _create_client() -> redis.Redis | None:
    if not settings.redis_url:
        return None
    try:
        return redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
        )
    except Exception:
        return None


r = _create_client()


def redis_healthy() -> bool:
    """Ping Redis để phục vụ readiness probe GET /ready."""
    if r is None:
        return False
    try:
        return bool(r.ping())
    except Exception:
        return False
