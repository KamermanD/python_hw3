import os
import sys
from dotenv import load_dotenv
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, src_path)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from sqlalchemy import create_engine  
from sqlalchemy import pool
from sqlalchemy.engine import URL  

from logging.config import fileConfig
from src.models import Base
from alembic import context

from src.core.config import settings


database_url_str = settings.database_sync_dsn

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata




def run_migrations_offline() -> None:

    context.configure(
        url=database_url_str,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    
    connectable = create_engine(database_url_str, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
