from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import MetaData
from alembic import context
import os
import sys
from typing import Any, Optional

# Add the parent directory to Python path to ensure app module can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Type hints for IDE - these will be resolved at runtime
settings: Any = None
Base: Any = None
target_metadata: Optional[MetaData] = None

# Try to import the app modules
try:
    # Use a more robust import method
    import importlib.util

    # Import config
    config_spec = importlib.util.spec_from_file_location(
        "app.core.config",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app",
            "core",
            "config.py",
        ),
    )
    if config_spec and config_spec.loader:
        config_module = importlib.util.module_from_spec(config_spec)
        config_spec.loader.exec_module(config_module)
        if hasattr(config_module, "settings"):
            settings = config_module.settings

    # Import database
    db_spec = importlib.util.spec_from_file_location(
        "app.core.database",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app",
            "core",
            "database.py",
        ),
    )
    if db_spec and db_spec.loader:
        db_module = importlib.util.module_from_spec(db_spec)
        db_spec.loader.exec_module(db_module)
        if hasattr(db_module, "Base"):
            Base = db_module.Base

    # Import models
    models_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "models"
    )
    if os.path.exists(models_path):
        for file in os.listdir(models_path):
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file[:-3]
                model_spec = importlib.util.spec_from_file_location(
                    f"app.models.{module_name}", os.path.join(models_path, file)
                )
                if model_spec and model_spec.loader:
                    model_module = importlib.util.module_from_spec(model_spec)
                    model_spec.loader.exec_module(model_module)

except Exception as e:
    print(f"Error importing app modules: {e}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")

    # If imports fail, we'll create minimal placeholders
    # This allows alembic to run but without autogenerate support
    class MockSettings:
        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chat_resume.db")

    class MockBase:
        metadata = None

    settings = MockSettings()
    Base = MockBase()

    print("Using mock settings and Base - autogenerate support disabled")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
if hasattr(Base, "metadata") and Base.metadata is not None:
    target_metadata = Base.metadata  # type: ignore
else:
    target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url() -> str:
    return str(settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration: dict[str, Any] = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
