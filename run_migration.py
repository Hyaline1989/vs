#!/usr/bin/env python3
# run_migration.py
import sys
import os

# Добавляем текущую папку в путь поиска модулей
sys.path.insert(0, os.path.dirname(__file__))

from alembic.config import Config
from alembic import command

def run_migrations():
    print("🔄 Запуск миграций...")
    
    # Создаём конфиг Alembic
    alembic_cfg = Config("alembic.ini")
    
    try:
        # Применяем все миграции
        command.upgrade(alembic_cfg, "head")
        print("✅ Миграции успешно применены!")
        return True
    except Exception as e:
        print(f"❌ Ошибка при применении миграций: {e}")
        return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)