import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError

from schoolpass.db.session import apply_invalid_tenant_context, apply_tenant_context
from schoolpass.identity.models import StaffProfile
from schoolpass.tenancy.context import TenantContext


async def test_app_role_nobypassrls(engine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'schoolpass_app'"))
        value = result.scalar_one()
        assert value is False


async def test_rls_enabled_and_forced(engine) -> None:
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    """
                    SELECT relrowsecurity, relforcerowsecurity
                    FROM pg_class
                    WHERE relname = 'staff_profiles'
                    """
                )
            )
        ).one()
        assert row[0] is True
        assert row[1] is True


async def test_tenant_a_cannot_select_tenant_b(db_factory, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_a"], user_id=world["user_a"]),
            )
            rows = (await session.execute(select(StaffProfile))).scalars().all()
            assert {row.tenant_id for row in rows} == {world["tenant_a"]}
            other = (
                (await session.execute(select(StaffProfile).where(StaffProfile.tenant_id == world["tenant_b"])))
                .scalars()
                .all()
            )
            assert other == []


async def test_tenant_a_cannot_insert_into_tenant_b(db_factory, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_a"], user_id=world["user_a"]),
            )
            session.add(
                StaffProfile(
                    tenant_id=world["tenant_b"],
                    user_id=world["user_a"],
                    staff_type="teacher",
                    employee_code="cross",
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()


async def test_tenant_a_cannot_update_tenant_b(db_factory, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_b"], user_id=world["user_b"]),
            )
            target_id = (await session.execute(select(StaffProfile))).scalar_one().id
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_a"], user_id=world["user_a"]),
            )
            result = await session.execute(
                update(StaffProfile).where(StaffProfile.id == target_id).values(employee_code="hacked")
            )
            assert result.rowcount == 0


async def test_tenant_a_cannot_delete_tenant_b(db_factory, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_a"], user_id=world["user_a"]),
            )
            result = await session.execute(delete(StaffProfile).where(StaffProfile.tenant_id == world["tenant_b"]))
            assert result.rowcount == 0


async def test_missing_tenant_context_fails_closed(db_factory, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="user", tenant_id=None, user_id=None))
            rows = (await session.execute(select(StaffProfile))).scalars().all()
            assert rows == []
            session.add(
                StaffProfile(
                    tenant_id=world["tenant_a"],
                    user_id=world["user_a"],
                    staff_type="teacher",
                    employee_code="no-ctx",
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()


async def test_invalid_tenant_context_fails_closed(db_factory, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_invalid_tenant_context(session)
            with pytest.raises(DBAPIError):
                await session.execute(select(StaffProfile))


async def test_pool_does_not_leak_tenant_context(db_factory, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_a"], user_id=world["user_a"]),
            )
            assert (await session.execute(select(StaffProfile))).scalars().first() is not None
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="user", tenant_id=None, user_id=None))
            assert (await session.execute(select(StaffProfile))).scalars().all() == []


async def test_worker_context_cannot_read_wrong_tenant(db_factory, world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="worker", tenant_id=world["tenant_a"], user_id=None),
            )
            rows = (await session.execute(select(StaffProfile))).scalars().all()
            assert all(row.tenant_id == world["tenant_a"] for row in rows)
            assert not any(row.tenant_id == world["tenant_b"] for row in rows)
