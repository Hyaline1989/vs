"""Run explicitly after approval: python scripts/migrate_departments.py --database /absolute/path/requirements.db --apply"""
import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from contextlib import closing

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from access_policy import migrate


def main():
    parser = argparse.ArgumentParser(description='Добавить отделы, сохранив текущие права. Создаёт резервную копию.')
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    if not args.apply:
        print('Без --apply изменений нет. База:', path)
        return
    backup = path.with_name(path.name + '.departments-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
    with closing(sqlite3.connect(str(path))) as conn, conn:
        with closing(sqlite3.connect(str(backup))) as copy:
            conn.backup(copy)
        conn.execute('BEGIN IMMEDIATE')
        migrate(conn)
    print('Готово. Резервная копия:', backup)


if __name__ == '__main__':
    main()
