"""Добавляет право payroll без изменения существующих разрешений."""
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime


def migrate(conn):
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_module_permissions'").fetchone()[0]
    if "'payroll'" in sql or 'CHECK' not in sql.upper():
        return
    if "'reports'" not in sql:
        raise ValueError('Сначала требуется актуальная схема прав на отчёты')
    before = conn.execute('SELECT * FROM user_module_permissions ORDER BY id').fetchall()
    indexes = [r[0] for r in conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='user_module_permissions' AND sql IS NOT NULL")]
    new_sql = sql.replace('user_module_permissions', 'user_module_permissions_payroll_new', 1).replace("'reports'", "'reports', 'payroll'")
    conn.execute(new_sql)
    conn.execute('INSERT INTO user_module_permissions_payroll_new SELECT * FROM user_module_permissions')
    conn.execute('DROP TABLE user_module_permissions')
    conn.execute('ALTER TABLE user_module_permissions_payroll_new RENAME TO user_module_permissions')
    for index in indexes:
        conn.execute(index)
    assert conn.execute('SELECT * FROM user_module_permissions ORDER BY id').fetchall() == before


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    if not args.apply:
        print('Без --apply база не изменяется.')
    else:
        with sqlite3.connect(path) as conn:
            backup = path.with_name(path.name + '.payroll-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
            with sqlite3.connect(backup) as copy:
                conn.backup(copy)
            conn.execute('BEGIN IMMEDIATE')
            migrate(conn)
        print('Право подготовлено. Старые разрешения сохранены. Backup:', backup)
