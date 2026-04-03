import asyncio
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from opensoar.config import settings
from opensoar.db import Base
import opensoar.models  # noqa: F401 — ensure all models are imported
from opensoar.plugins import (
    configure_alembic_version_locations,
    get_plugin_migration_config,
    import_optional_plugin_models,
)

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

import_optional_plugin_models()
plugin_migration_config = get_plugin_migration_config()
configure_alembic_version_locations(
    config,
    core_versions_path=str((Path(__file__).resolve().parent / "versions").resolve()),
    plugin_version_locations=plugin_migration_config.version_locations,
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
