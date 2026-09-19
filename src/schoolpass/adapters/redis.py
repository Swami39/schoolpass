from __future__ import annotations

from typing import Protocol

from redis.asyncio import Redis


class Cache(Protocol):
    async def ping(self) -> bool: ...
    async def set_nx(self, key: str, value: str, ex: int) -> bool: ...
    async def set(self, key: str, value: str, ex: int | None = None) -> None: ...
    async def get(self, key: str) -> bytes | None: ...
    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> None: ...
    async def delete(self, *keys: str) -> None: ...
    async def close(self) -> None: ...


class RedisCache:
    def __init__(self, url: str) -> None:
        self._client = Redis.from_url(url)

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def set_nx(self, key: str, value: str, ex: int) -> bool:
        return bool(await self._client.set(key, value, ex=ex, nx=True))

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        await self._client.set(key, value, ex=ex)

    async def get(self, key: str) -> bytes | None:
        value = await self._client.get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        return str(value).encode("utf-8")

    async def incr(self, key: str) -> int:
        return int(await self._client.incr(key))

    async def expire(self, key: str, seconds: int) -> None:
        await self._client.expire(key, seconds)

    async def delete(self, *keys: str) -> None:
        if keys:
            await self._client.delete(*keys)

    async def close(self) -> None:
        await self._client.aclose()
