"""Явная миграция ставок с резервной копией. Не запускает приложение."""
import argparse
import sqlite3
import sys
from pathlib import Path
from contextlib import closing
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from candidate_rates import create_schema, sync_priority_rates


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    if not args.apply:
        print('Для добавления таблиц ставок используйте --apply. База не изменена.')
    else:
        with closing(sqlite3.connect(path)) as conn:
            backup = path.with_name(path.name + '.rates-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
            with closing(sqlite3.connect(backup)) as copy:
                conn.backup(copy)
            with conn:
                create_schema(conn)
                changed = sync_priority_rates(conn)
        print('Автоматически заполнено/обновлено ставок:', changed)
        print('Таблицы ставок подготовлены. Резервная копия:', backup)
