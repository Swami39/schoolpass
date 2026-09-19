from __future__ import annotations

from typing import Any, Protocol


class OtpSender(Protocol):
    async def send(self, destination: str, code: str) -> None: ...


class ProductionOtpSender:
    """Production SMS/email sender is a later-phase integration."""

    async def send(self, destination: str, code: str) -> None:
        raise RuntimeError("OTP delivery provider is not configured for this environment")


class DevOtpStore:
    """Local/test only: stores hashed OTP send records in Redis. Never used in production."""

    def __init__(self, redis: Any, *, allow: bool) -> None:
        self._redis = redis
        self._allow = allow

    async def send(self, destination: str, code: str) -> None:
        if not self._allow:
            raise RuntimeError("Dev OTP capture is disabled")
        key = f"otp:dev:{destination}"
        await self._redis.set(key, code, ex=300)

    async def peek(self, destination: str) -> str | None:
        if not self._allow:
            return None
        value = await self._redis.get(f"otp:dev:{destination}")
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)
