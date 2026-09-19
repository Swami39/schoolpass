from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from schoolpass.db.session import Base
from schoolpass.identity import models as _models  # noqa: F401
from schoolpass.people import models as _people_models  # noqa: F401
from schoolpass.cards import models as _card_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _migrator_url() -> str:
    from schoolpass.config import get_settings

    get_settings.cache_clear()
    return get_settings().database_url_migrator


def run_migrations_offline() -> None:
    url = _migrator_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_migrator_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        do_run_migrations(connection)
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
