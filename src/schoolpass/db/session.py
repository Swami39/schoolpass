from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from schoolpass.tenancy.context import TenantContext

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_engine(url: str, *, pool_size: int = 10, null_pool: bool = False) -> AsyncEngine:
    if null_pool:
        return create_async_engine(url, poolclass=NullPool)
    return create_async_engine(
        url,
        pool_size=pool_size,
        max_overflow=20,
        pool_pre_ping=True,
    )


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def apply_tenant_context(session: AsyncSession, ctx: TenantContext) -> None:
    """SET LOCAL via set_config(..., is_local=true). Never session-sticky SET."""
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": ctx.tenant_guc()},
    )
    await session.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": ctx.user_guc()},
    )
    await session.execute(
        text("SELECT set_config('app.actor_type', :actor_type, true)"),
        {"actor_type": ctx.actor_type},
    )


async def apply_invalid_tenant_context(session: AsyncSession) -> None:
    await session.execute(text("SELECT set_config('app.tenant_id', 'not-a-uuid', true)"))
    await session.execute(text("SELECT set_config('app.user_id', '', true)"))
    await session.execute(text("SELECT set_config('app.actor_type', 'user', true)"))


async def tenant_session(
    factory: async_sessionmaker[AsyncSession],
    ctx: TenantContext,
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, ctx)
            yield session


def as_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
