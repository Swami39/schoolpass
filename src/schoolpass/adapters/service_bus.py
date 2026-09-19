from __future__ import annotations

import json
from typing import Any, Protocol

from schoolpass.adapters.redis import RedisCache
from schoolpass.observability.logging import get_logger

log = get_logger("schoolpass.bus")


class MessageBus(Protocol):
    async def publish(self, topic: str, message: dict[str, Any]) -> None: ...
    async def close(self) -> None: ...


class LocalRedisBus:
    """Local/test transport. Failures are real Redis errors, not swallowed success."""

    def __init__(self, cache: RedisCache) -> None:
        self._cache = cache

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        payload = json.dumps(
            {
                "topic": topic,
                "message_id": message.get("id"),
                "tenant_id": message.get("tenant_id"),
                "idempotency_key": message.get("idempotency_key"),
                "schema_version": message.get("schema_version"),
                "payload": message.get("payload"),
            }
        )
        await self._cache._client.rpush(f"bus:{topic}", payload)  # noqa: SLF001
        log.info("bus_published", topic=topic, message_id=message.get("id"))

    async def close(self) -> None:
        return None


class AzureServiceBus:
    def __init__(self, fully_qualified_namespace: str) -> None:
        if not fully_qualified_namespace:
            raise RuntimeError("Azure Service Bus namespace is not configured")
        self._namespace = fully_qualified_namespace

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        raise RuntimeError(
            "Azure Service Bus publisher is not enabled in this environment. "
            "Configure workload identity and SERVICE_BUS_MODE=azure in a later ops phase."
        )

    async def close(self) -> None:
        return None
