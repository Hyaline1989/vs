"""Explicit SQLite migration to allow the new agent user role."""
import argparse
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime
from pathlib import Path


USER_COLUMNS = ('id', 'username', 'password_hash', 'full_name', 'email', 'role',
                'created_by', 'created_at', 'is_active', 'last_login')
USER_TABLE_SQL = '''
    CREATE TABLE users_role_upgrade (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        email TEXT,
        role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'viewer', 'agent')),
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        last_login TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
'''


def migrate(conn):
    schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if not schema:
        raise ValueError('Таблица users не найдена')
    if "'agent'" in schema[0]:
        return False
    if "CHECK(role IN ('admin', 'manager', 'viewer'))" not in schema[0]:
        raise ValueError('Структура ролей отличается от ожидаемой; обновление остановлено')
    columns = tuple(row[1] for row in conn.execute('PRAGMA table_info(users)'))
    if columns != USER_COLUMNS:
        raise ValueError('Структура users отличается от ожидаемой; обновление остановлено')
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='users_role_upgrade'").fetchone():
        raise ValueError('В базе уже есть временная таблица users_role_upgrade')
    if conn.execute("SELECT 1 FROM sqlite_master WHERE tbl_name='users' AND type='trigger'").fetchone():
        raise ValueError('Найдены триггеры users; обновление остановлено')
    indexes = [row[0] for row in conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name='users' AND type='index' AND sql IS NOT NULL")]

    before_users = conn.execute('SELECT * FROM users ORDER BY id').fetchall()
    before_foreign_keys = conn.execute('PRAGMA foreign_key_check').fetchall()
    sequence = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='users'").fetchone()
    conn.execute('PRAGMA foreign_keys=OFF')
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(USER_TABLE_SQL)
        names = ','.join(USER_COLUMNS)
        conn.execute(f'INSERT INTO users_role_upgrade ({names}) SELECT {names} FROM users')
        conn.execute('DROP TABLE users')
        conn.execute('ALTER TABLE users_role_upgrade RENAME TO users')
        for index_sql in indexes:
            conn.execute(index_sql)
        if sequence:
            conn.execute("UPDATE sqlite_sequence SET seq=? WHERE name='users'", sequence)
        if conn.execute('SELECT * FROM users ORDER BY id').fetchall() != before_users:
            raise ValueError('Данные пользователей изменились; обновление отменено')
        after_foreign_keys = conn.execute('PRAGMA foreign_key_check').fetchall()
        before_issues, after_issues = Counter(before_foreign_keys), Counter(after_foreign_keys)
        if after_issues != before_issues:
            added = list((after_issues - before_issues).elements())[:5]
            removed = list((before_issues - after_issues).elements())[:5]
            raise ValueError(f'Связи изменились; обновление отменено. До: {len(before_foreign_keys)}, после: {len(after_foreign_keys)}; добавились: {added}; исчезли: {removed}')
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Проверка целостности базы не пройдена; обновление отменено')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute('PRAGMA foreign_keys=ON')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--diagnose', action='store_true', help='Test migration on an in-memory copy only')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    with closing(sqlite3.connect(str(path))) as conn:
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        if not sql:
            raise ValueError('Таблица users не найдена')
        if "'agent'" in sql[0]:
            print('Роль agent уже разрешена; изменений нет.')
            return
        if args.diagnose:
            with closing(sqlite3.connect(':memory:')) as copy:
                conn.backup(copy)
                migrate(copy)
            print('Проверка на копии прошла; серверная база не изменена.')
            return
        if not args.apply:
            print('Проверка: роли agent ещё нет. Для обновления добавьте --apply.')
            return
        backup = path.with_name(path.name + '.before-agent-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        with closing(sqlite3.connect(str(backup))) as copy:
            conn.backup(copy)
        if migrate(conn):
            print('Роль agent добавлена. Существующие пользователи не изменены.')
            print('Резервная копия:', backup)


if __name__ == '__main__':
    main()
