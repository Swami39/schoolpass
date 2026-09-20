from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from schoolpass.api.main import create_app
from schoolpass.auth.passwords import hash_password
from schoolpass.config import Settings, get_settings
from schoolpass.db.session import apply_tenant_context, create_engine, session_factory
from schoolpass.identity.models import Role, StaffProfile, Tenant, TenantMembership, User
from schoolpass.tenancy.context import TenantContext

pytest_plugins = ["fixtures_students"]


def _rsa_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture(scope="session")
def jwt_keys() -> tuple[str, str]:
    return _rsa_pair()


@pytest.fixture(scope="session")
def settings(jwt_keys: tuple[str, str]) -> Settings:
    private_pem, public_pem = jwt_keys
    get_settings.cache_clear()
    os.environ["DIRECTORY_BOOTSTRAP_PASSWORD"] = "Test-Directory-Only-2026"
    return Settings(
        app_env="test",
        otp_dev_allow=True,
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://schoolpass_app:app_dev_only@localhost:5432/schoolpass",
        ),
        database_url_migrator=os.environ.get(
            "DATABASE_URL_MIGRATOR",
            "postgresql+psycopg://schoolpass_migrator:migrator_dev_only@localhost:5432/schoolpass",
        ),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        jwt_private_key_pem=private_pem,
        jwt_public_key_pem=public_pem,
        secret_app_key="test-secret-key-not-production",
        directory_bootstrap_password="Test-Directory-Only-2026",
    )


@pytest.fixture(scope="session", autouse=True)
def migrate(settings: Settings) -> None:
    from alembic import command
    from alembic.config import Config

    os.environ["DATABASE_URL_MIGRATOR"] = settings.database_url_migrator
    os.environ["DATABASE_URL"] = settings.database_url
    os.environ["APP_ENV"] = "test"
    os.environ["OTP_DEV_ALLOW"] = "true"
    os.environ["JWT_PRIVATE_KEY_PEM"] = settings.jwt_private_key_pem
    os.environ["JWT_PUBLIC_KEY_PEM"] = settings.jwt_public_key_pem
    os.environ["DIRECTORY_BOOTSTRAP_PASSWORD"] = settings.directory_bootstrap_password
    get_settings.cache_clear()
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture
async def engine(settings: Settings):
    engine = create_engine(settings.database_url, pool_size=5, null_pool=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_factory(engine):
    return session_factory(engine)


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def world(db_factory) -> dict[str, UUID]:
    """Synthetic adult users only — no student records."""
    password = hash_password("correct-horse-battery")
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            roles = {
                row.name: row for row in (await session.execute(select(Role).where(Role.is_system.is_(True)))).scalars()
            }
            tenant_a = Tenant(id=uuid4(), legal_name="North Test School", slug=f"north-{uuid4().hex[:8]}")
            tenant_b = Tenant(id=uuid4(), legal_name="South Test School", slug=f"south-{uuid4().hex[:8]}")
            session.add_all([tenant_a, tenant_b])
            user_a = User(
                id=uuid4(),
                email=f"teacher-a-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            user_b = User(
                id=uuid4(),
                email=f"teacher-b-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            session.add_all([user_a, user_b])
            await session.flush()
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_a.id, user_id=user_a.id),
            )
            session.add_all(
                [
                    TenantMembership(
                        tenant_id=tenant_a.id,
                        user_id=user_a.id,
                        role_id=roles["teacher"].id,
                    ),
                    StaffProfile(
                        tenant_id=tenant_a.id,
                        user_id=user_a.id,
                        staff_type="teacher",
                        employee_code="A-1",
                    ),
                ]
            )
            await session.flush()
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_b.id, user_id=user_b.id),
            )
            session.add_all(
                [
                    TenantMembership(
                        tenant_id=tenant_b.id,
                        user_id=user_b.id,
                        role_id=roles["teacher"].id,
                    ),
                    StaffProfile(
                        tenant_id=tenant_b.id,
                        user_id=user_b.id,
                        staff_type="teacher",
                        employee_code="B-1",
                    ),
                ]
            )
            await session.flush()
            return {
                "tenant_a": tenant_a.id,
                "tenant_b": tenant_b.id,
                "user_a": user_a.id,
                "user_b": user_b.id,
                "email_a": user_a.email,
                "email_b": user_b.email,
            }
