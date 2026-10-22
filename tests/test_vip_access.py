"""VIP не должен наследоваться от роли или сохраняться после её снятия."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from database import users
from database.vip import has_vip_access, vip_access_ready


class VipAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / 'test.db'
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT NOT NULL)')
            conn.executemany('INSERT INTO users(id, role) VALUES(?, ?)',
                             [(1, 'admin'), (2, 'admin'), (3, 'viewer')])

    def test_default_is_closed_except_system_admin(self):
        self.assertFalse(vip_access_ready(self.database))
        self.assertTrue(has_vip_access(1, self.database))
        self.assertFalse(has_vip_access(2, self.database))
        self.assertFalse(has_vip_access(3, self.database))

    def test_demoting_admin_removes_vip_and_repromotion_does_not_restore_it(self):
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.execute('CREATE TABLE user_vip_access(user_id INTEGER PRIMARY KEY)')
        with patch.object(users, 'DB_NAME', str(self.database)):
            self.assertTrue(users.update_user(2, {'vip_access': True}))
            self.assertTrue(has_vip_access(2, self.database))
            self.assertTrue(users.update_user(2, {'role': 'manager'}))
            self.assertFalse(has_vip_access(2, self.database))
            self.assertTrue(users.update_user(2, {'role': 'admin'}))
            self.assertFalse(has_vip_access(2, self.database))

    def test_non_admin_cannot_use_a_stale_vip_row(self):
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.execute('CREATE TABLE user_vip_access(user_id INTEGER PRIMARY KEY)')
            conn.execute('INSERT INTO user_vip_access(user_id) VALUES(3)')
        self.assertFalse(has_vip_access(3, self.database))

    def test_without_migration_grant_fails_without_changing_role(self):
        with patch.object(users, 'DB_NAME', str(self.database)):
            self.assertFalse(users.update_user(3, {'role': 'admin', 'vip_access': True}))
        with closing(sqlite3.connect(self.database)) as conn, conn:
            self.assertEqual(conn.execute('SELECT role FROM users WHERE id=3').fetchone()[0], 'viewer')


if __name__ == '__main__':
    unittest.main()
