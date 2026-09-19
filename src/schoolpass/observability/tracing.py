from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Hook for a later tracing backend (OpenTelemetry). Attributes stay local."""
    del name, attributes
    yield
