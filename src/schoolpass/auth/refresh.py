from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.config import Settings
from schoolpass.db.mixins import utcnow
from schoolpass.errors import AuthenticationError
from schoolpass.identity.models import RefreshToken


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


async def issue_refresh_token(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    device_id: UUID | None,
    family_id: UUID | None = None,
) -> tuple[str, RefreshToken]:
    raw = new_refresh_token()
    row = RefreshToken(
        user_id=user_id,
        device_id=device_id,
        family_id=family_id or uuid4(),
        token_hash=hash_refresh_token(raw),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
    )
    session.add(row)
    await session.flush()
    return raw, row


async def rotate_refresh_token(
    session: AsyncSession,
    settings: Settings,
    raw_token: str,
    *,
    device_id: UUID | None,
) -> tuple[str, RefreshToken]:
    token_hash = hash_refresh_token(raw_token)
    result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    current = result.scalar_one_or_none()
    if current is None:
        raise AuthenticationError("Invalid refresh token")
    if current.revoked_at is not None or current.expires_at <= utcnow():
        if current.revoked_at is None:
            current.revoked_at = utcnow()
        await _revoke_family(session, current.family_id)
        raise AuthenticationError("Refresh token reuse detected")
    current.revoked_at = utcnow()
    return await issue_refresh_token(
        session,
        settings,
        user_id=current.user_id,
        device_id=device_id or current.device_id,
        family_id=current.family_id,
    )


async def revoke_family(session: AsyncSession, family_id: UUID) -> None:
    await _revoke_family(session, family_id)


async def revoke_user_refresh_tokens(session: AsyncSession, user_id: UUID) -> None:
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = utcnow()
    for row in result.scalars():
        row.revoked_at = now


async def _revoke_family(session: AsyncSession, family_id: UUID) -> None:
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = utcnow()
    for row in result.scalars():
        row.revoked_at = now
