from __future__ import annotations

from pathlib import Path
from typing import Protocol


class BlobStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...


class LocalBlobStore:
    """Filesystem blob adapter for local/test. Not a mock success path."""

    def __init__(self, root: str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("..", "")
        path = (self._root / safe).resolve()
        if not str(path).startswith(str(self._root.resolve())):
            raise ValueError("invalid blob key")
        return path

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.with_suffix(path.suffix + ".meta").write_text(content_type, encoding="utf-8")

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(key)
        return path.read_bytes()
