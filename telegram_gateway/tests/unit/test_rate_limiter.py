"""Unit tests for webhook/rate_limiter.py, using FakeRedis (tests/fakes.py)
in place of a real Redis connection — the counting logic is what's under
test, not Redis itself."""
from __future__ import annotations

from src.webhook.rate_limiter import RateLimiter
from tests.fakes import FakeRedis


async def test_allows_requests_under_the_limit():
    limiter = RateLimiter(FakeRedis(), limit_per_window=3)

    assert await limiter.is_allowed(chat_id=1) is True
    assert await limiter.is_allowed(chat_id=1) is True
    assert await limiter.is_allowed(chat_id=1) is True


async def test_rejects_requests_over_the_limit():
    limiter = RateLimiter(FakeRedis(), limit_per_window=2)

    assert await limiter.is_allowed(chat_id=1) is True
    assert await limiter.is_allowed(chat_id=1) is True
    assert await limiter.is_allowed(chat_id=1) is False


async def test_limits_are_tracked_independently_per_chat():
    limiter = RateLimiter(FakeRedis(), limit_per_window=1)

    assert await limiter.is_allowed(chat_id=1) is True
    assert await limiter.is_allowed(chat_id=2) is True  # a different chat, unaffected by chat 1's count
    assert await limiter.is_allowed(chat_id=1) is False
