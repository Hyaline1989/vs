"""Однократное включение хранения права VIP с резервной копией базы."""

import argparse
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Добавить отдельное право VIP. Изначально включено только для системного администратора.')
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    with closing(sqlite3.connect(str(path))) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_vip_access'"
        ).fetchone() is not None
        if exists:
            print('Право VIP уже подготовлено; база не менялась.')
            return
        if not args.apply:
            print('Проверка: таблицы права VIP пока нет. Для добавления укажите --apply.')
            return
        backup = path.with_name(path.name + '.vip-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        with closing(sqlite3.connect(str(backup))) as copy:
            conn.backup(copy)
        with conn:
            conn.execute('''CREATE TABLE user_vip_access (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE
            )''')
    print('Право VIP подготовлено. У обычных администраторов выключено.')
    print('Резервная копия:', backup)


if __name__ == '__main__':
    main()
