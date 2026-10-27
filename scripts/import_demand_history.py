"""Перенос старой потребности. Без --apply только предварительный просмотр."""
import argparse
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.preview_demand_history_import import preview

LEGACY_SCHEMA = '''CREATE TABLE IF NOT EXISTS demand_history_legacy (
    day TEXT NOT NULL, object_name TEXT NOT NULL,
    PRIMARY KEY(day,object_name))'''


def transfer(conn, start, end):
    """Caller owns transaction; existing archive entries are never updated."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='demand_history'").fetchone():
        raise ValueError('Сначала выполните migrate_demand_history.py')
    rows, orphaned = preview(conn, start, end)
    if orphaned:
        raise ValueError('Обнаружены строки без объекта. Перенос отменён.')
    conn.execute(LEGACY_SCHEMA)
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    inserted = 0
    for day, name, count, exists in rows:
        if exists:
            continue
        cur = conn.execute('''INSERT INTO demand_history(day,object_name,count,saved_at)
            VALUES(?,?,?,?) ON CONFLICT(day,object_name) DO NOTHING''', (day,name,count,stamp))
        if cur.rowcount:
            conn.execute('INSERT INTO demand_history_legacy(day,object_name) VALUES(?,?)', (day,name))
            inserted += 1
    return inserted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--from', dest='start', required=True, type=date.fromisoformat)
    parser.add_argument('--to', dest='end', required=True, type=date.fromisoformat)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.start > args.end:
        parser.error('Начало периода позже окончания')
    path = Path(args.database).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as read:
        rows, orphaned = preview(read, args.start, args.end)
        print('К переносу:', sum(not r[3] for r in rows))
        print('Уже в архиве (не изменятся):', sum(r[3] for r in rows))
        if orphaned:
            raise ValueError('Есть строки без объекта. Перенос отменён.')
        if not args.apply:
            print('База не изменена. Для переноса добавьте --apply.')
            return
        backup = path.with_name(path.name+'.before-demand-import-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.bak')
        with closing(sqlite3.connect(backup)) as target:
            read.backup(target)
        print('Резервная копия:', backup)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            count = transfer(conn, args.start, args.end)
    print('Успешно перенесено:', count)
    print('Существующая история и исходные данные не изменены.')


if __name__ == '__main__':
    main()
