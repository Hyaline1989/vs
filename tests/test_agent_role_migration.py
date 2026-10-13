"""Migration checks on an isolated in-memory database."""
import sqlite3
import unittest

from scripts.add_agent_role import migrate


class AgentRoleMigrationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.executescript('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                email TEXT,
                role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'viewer')),
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                last_login TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            );
            CREATE TABLE user_module_permissions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                module_name TEXT
            );
            CREATE INDEX idx_users_role ON users(role);
            INSERT INTO users(id,username,password_hash,role) VALUES
                (1,'admin','hash1','admin'),(2,'viewer','hash2','viewer');
            INSERT INTO user_module_permissions VALUES(1,2,'selection');
        ''')
        self.conn.commit()

    def test_preserves_existing_rows_and_allows_agent(self):
        before = self.conn.execute('SELECT * FROM users ORDER BY id').fetchall()
        self.assertTrue(migrate(self.conn))
        self.assertEqual(before, self.conn.execute('SELECT * FROM users ORDER BY id').fetchall())
        self.assertEqual(self.conn.execute('SELECT user_id FROM user_module_permissions').fetchall(), [(2,)])
        self.assertIsNotNone(self.conn.execute("SELECT name FROM sqlite_master WHERE name='idx_users_role'").fetchone())
        self.assertEqual(self.conn.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.conn.execute("INSERT INTO users(username,password_hash,role) VALUES('agent','hash3','agent')")
        self.conn.commit()
        self.assertEqual(self.conn.execute("SELECT role FROM users WHERE username='agent'").fetchone()[0], 'agent')
        self.assertFalse(migrate(self.conn))

    def test_unexpected_schema_stays_untouched(self):
        self.conn.execute('ALTER TABLE users ADD COLUMN unexpected TEXT')
        with self.assertRaises(ValueError):
            migrate(self.conn)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM users').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
