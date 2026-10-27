"""Добавляет архив, не заполняет прошлые дни предположительными значениями."""
import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from contextlib import closing
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demand_history import SCHEMA


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as read:
        if read.execute("SELECT 1 FROM sqlite_master WHERE name='demand_history' AND type='table'").fetchone():
            print('Архив уже создан. Изменений нет.')
            return
        if not args.apply:
            print('Архива пока нет. Для создания запустите с --apply. Старые данные не изменятся.')
            return
        backup = path.with_name(path.name + '.demand-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        with closing(sqlite3.connect(backup)) as target:
            read.backup(target)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute(SCHEMA)
    print('Архив создан. Запись начнётся при следующем сохранении потребности.')
    print('Резервная копия:', backup)


if __name__ == '__main__':
    main()
