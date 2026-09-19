from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

ActorType = Literal["user", "device", "worker", "platform", "system"]


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Transaction-local authorization context. Never taken from client tenant headers."""

    actor_type: ActorType
    tenant_id: UUID | None = None
    user_id: UUID | None = None

    def tenant_guc(self) -> str:
        return str(self.tenant_id) if self.tenant_id is not None else ""

    def user_guc(self) -> str:
        return str(self.user_id) if self.user_id is not None else ""
