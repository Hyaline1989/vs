"""Отдельное право VIP; отсутствие таблицы означает закрытый доступ."""

import logging
import sqlite3
from contextlib import closing

from database.db_core import DB_NAME


logger = logging.getLogger(__name__)


def vip_access_ready(database_path=DB_NAME):
    with closing(sqlite3.connect(database_path)) as conn:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_vip_access'"
        ).fetchone() is not None


def has_vip_access(user_id, database_path=DB_NAME):
    if user_id == 1:
        with closing(sqlite3.connect(database_path)) as conn:
            row = conn.execute('SELECT role FROM users WHERE id=1').fetchone()
            return bool(row and row[0] == 'admin')
    try:
        with closing(sqlite3.connect(database_path)) as conn:
            return conn.execute(
                'SELECT 1 FROM user_vip_access v JOIN users u ON u.id=v.user_id '
                'WHERE u.id=? AND u.role=?', (user_id, 'admin')
            ).fetchone() is not None
    except sqlite3.OperationalError as error:
        if 'no such table: user_vip_access' not in str(error):
            logger.error('Не удалось проверить доступ VIP: %s', error)
        return False
