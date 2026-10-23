import sqlite3
import unittest
from unittest.mock import patch
import ast
from pathlib import Path
# Проверяем реальный метод без загрузки Flask и приложения.
tree = ast.parse(Path(__file__).resolve().parents[1].joinpath('models.py').read_text(encoding='utf-8'))
model = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'User')
method = next(n for n in model.body if isinstance(n, ast.FunctionDef) and n.name == 'can_view_module')
namespace = {}
exec(compile(ast.Module(body=[method], type_ignores=[]), 'models.py', 'exec'), namespace)


class User:
    can_view_module = namespace['can_view_module']
    def __init__(self, data):
        self.role = data['role']
    def is_system_admin(self):
        return False
    def is_admin(self):
        return self.role == 'admin'
from access_policy import migrate, effective
from scripts.migrate_payroll_access import migrate as migrate_payroll


class PayrollAccessTests(unittest.TestCase):
    def test_roles_default_denied_and_explicit_grant(self):
        for role in ('admin', 'manager', 'viewer', 'agent'):
            user = User(dict(id=2, username='test', password_hash='', role=role))
            user._module_permissions = {}
            with patch.object(User, 'is_system_admin', return_value=False):
                self.assertFalse(user.can_view_module('payroll'))
                user._module_permissions['payroll'] = True
                self.assertTrue(user.can_view_module('payroll'))
                user._module_permissions['payroll'] = False
                self.assertFalse(user.can_view_module('payroll'))
        with patch.object(User, 'is_system_admin', return_value=True):
            self.assertTrue(user.can_view_module('payroll'))

    def test_department_and_override(self):
        with sqlite3.connect(':memory:') as c:
            c.execute('CREATE TABLE objects_settings(id INTEGER)')
            migrate(c)
            c.execute('INSERT INTO access_departments VALUES(1,?,?)', ('Test', '{"modules":{"payroll":true}}'))
            c.execute('INSERT INTO access_memberships VALUES(2,1,?)', ('{}',))
            self.assertTrue(effective(c,2)[0]['payroll'])
            c.execute('UPDATE access_memberships SET overrides=?', ('{"modules":{"payroll":false}}',))
            self.assertFalse(effective(c,2)[0]['payroll'])

    def test_migration_preserves_old_permissions(self):
        with sqlite3.connect(':memory:') as c:
            c.execute("CREATE TABLE user_module_permissions(id INTEGER PRIMARY KEY, user_id INTEGER, module_name TEXT CHECK(module_name IN ('dashboard','reports')), can_view INTEGER)")
            c.execute("INSERT INTO user_module_permissions VALUES(1,2,'reports',1)")
            migrate_payroll(c)
            self.assertEqual(c.execute('SELECT * FROM user_module_permissions').fetchall(), [(1,2,'reports',1)])
            c.execute("INSERT INTO user_module_permissions VALUES(2,2,'payroll',1)")
            migrate_payroll(c)


if __name__ == '__main__':
    unittest.main()
