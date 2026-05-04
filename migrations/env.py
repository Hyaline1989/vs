# migrations/env.py
import sys
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Импортируем имя вашей БД
from database import DB_NAME

# Это для логирования
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Указываем путь к БД
config.set_main_option('sqlalchemy.url', f'sqlite:///{DB_NAME}')

# target_metadata = None, так как вы не используете SQLAlchemy ORM
target_metadata = None

# Включаем поддержку batch-режима для SQLite
def run_migrations_offline():
    """Запуск миграций в offline-режиме (только генерация SQL)"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Запуск миграций в online-режиме (реальное применение к БД)"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # ВАЖНО: включаем batch-режим для SQLite
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # это ключевая опция для SQLite!
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()