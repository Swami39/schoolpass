from __future__ import annotations

from typing import Any


class MetricsSink:
    """Hook for a later metrics backend. Does not emit to a fake remote service."""

    def increment(self, name: str, value: int = 1, **labels: Any) -> None:
        return None

    def observe(self, name: str, value: float, **labels: Any) -> None:
        return None


metrics = MetricsSink()
