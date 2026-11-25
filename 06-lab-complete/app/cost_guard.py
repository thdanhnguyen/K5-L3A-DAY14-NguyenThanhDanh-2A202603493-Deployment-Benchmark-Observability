"""
Cost guard (tiêu chí 8) — Cộng dồn chi phí LLM vào Redis, vượt budget → HTTP 402.
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_fallback_daily_cost: dict[str, float] = {}


def _daily_key() -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"cost:daily:{day}"


def _monthly_key() -> str:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return f"cost:monthly:{month}"


def _get_cost(key: str) -> float:
    if r is not None:
        try:
            val = r.get(key)
            return float(val) if val is not None else 0.0
        except Exception:
            pass
    return _fallback_daily_cost.get(key, 0.0)


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget ngày hoặc tháng → raise HTTPException(status_code=402)."""
    daily_used = _get_cost(_daily_key())
    if daily_used >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "used_usd": round(daily_used, 6),
                "budget_usd": settings.daily_budget_usd,
            },
        )

    monthly_used = _get_cost(_monthly_key())
    if monthly_used >= settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(monthly_used, 6),
                "budget_usd": settings.monthly_budget_usd,
            },
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng trong Redis, trả về chi phí request."""
    cost = (
        (input_tokens / 1000.0) * PRICE_INPUT_PER_1K
        + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    )
    d_key = _daily_key()
    m_key = _monthly_key()

    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.incrbyfloat(d_key, cost)
            pipe.expire(d_key, 2 * 24 * 3600)
            pipe.incrbyfloat(m_key, cost)
            pipe.expire(m_key, 32 * 24 * 3600)
            pipe.execute()
            return round(cost, 6)
        except Exception:
            pass

    _fallback_daily_cost[d_key] = _fallback_daily_cost.get(d_key, 0.0) + cost
    _fallback_daily_cost[m_key] = _fallback_daily_cost.get(m_key, 0.0) + cost
    return round(cost, 6)
