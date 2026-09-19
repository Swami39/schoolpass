from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt

from schoolpass.config import Settings
from schoolpass.errors import AuthenticationError

ALGORITHM = "RS256"


def encode_access_token(
    settings: Settings,
    *,
    user_id: UUID,
    tenant_id: UUID | None,
    roles: list[str],
    mfa: bool,
    platform: bool,
    ttl: timedelta | None = None,
) -> str:
    if not settings.jwt_private_key_pem:
        raise RuntimeError("JWT private key is not configured")
    now = datetime.now(UTC)
    expires = now + (ttl or timedelta(minutes=settings.access_token_minutes))
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "ver": 1,
        "roles": roles,
        "mfa": mfa,
        "jti": str(uuid4()),
        "typ": "access",
    }
    if tenant_id is not None:
        payload["tid"] = str(tenant_id)
    if platform:
        payload["plat"] = True
    return jwt.encode(payload, settings.jwt_private_key_pem, algorithm=ALGORITHM)


def encode_mfa_token(settings: Settings, user_id: UUID) -> str:
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.mfa_challenge_minutes)
    payload = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": str(uuid4()),
        "typ": "mfa",
    }
    return jwt.encode(payload, settings.jwt_private_key_pem, algorithm=ALGORITHM)


def decode_token(settings: Settings, token: str) -> dict[str, Any]:
    if not settings.jwt_public_key_pem:
        raise RuntimeError("JWT public key is not configured")
    try:
        return jwt.decode(
            token,
            settings.jwt_public_key_pem,
            algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid token") from exc
