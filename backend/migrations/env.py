import asyncio
from logging.config import fileConfig

from sqlalchemy import inspect, pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.db.base import Base

# Import the complete model registry so Alembic autogenerate sees every table.
import app.modules.models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


LEGACY_BASE_REVISIONS = {
    # Older archives used either of these identifiers for the same installed
    # base generation. 7b478d243b18 is the real base revision in this tree.
    "cb0cf603f543": "7b478d243b18",
    "3797c9448715": "7b478d243b18",
}


def _repair_known_legacy_revision(connection: Connection) -> None:
    """Repair a known stale Alembic version only when the expected base schema exists.

    Older project archives used revision ``cb0cf603f543`` for the same installed
    base generation that is represented by ``7b478d243b18`` in this repository.
    Alembic refuses to start when the database still references that removed id.
    We never stamp blindly: the core base tables must already exist first.
    """
    inspector = inspect(connection)
    if not inspector.has_table("alembic_version"):
        return

    current = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    target = LEGACY_BASE_REVISIONS.get(current)
    if target is None:
        return

    required_tables = {
        "attributes", "categories", "users", "attribute_values", "products",
        "warehouses", "locations", "product_variants", "cycle_counts", "media",
        "product_default_locations", "product_items", "stock", "stock_openings",
        "cycle_count_lines", "labels", "qc_records", "stock_adjustments",
        "stock_movements", "stock_reservations", "stock_transfers",
    }
    missing = sorted(name for name in required_tables if not inspector.has_table(name))
    if missing:
        raise RuntimeError(
            "Database references legacy Alembic revision %s but its base schema is incomplete; "
            "refusing an automatic stamp. Missing tables: %s" % (current, ", ".join(missing))
        )

    connection.execute(
        text("UPDATE alembic_version SET version_num = :target WHERE version_num = :current"),
        {"target": target, "current": current},
    )


def do_run_migrations(connection: Connection) -> None:
    # Run legacy revision repair in its own committed transaction.
    # SQLAlchemy 2.x starts an implicit transaction even for SELECT/inspect
    # operations. If that transaction is left open, Alembic migrations may
    # appear to run but get rolled back when the connection closes.
    with connection.begin():
        _repair_known_legacy_revision(connection)

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
