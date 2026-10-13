"""Isolated in-memory database tests; never import app or open requirements.db."""
import sqlite3
import unittest
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from access_policy import migrate, effective, assign, validate_policy


class DepartmentTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT);
            CREATE TABLE objects_settings(id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE user_module_permissions(user_id INTEGER,module_name TEXT,can_view INTEGER);
            CREATE TABLE user_object_permissions(user_id INTEGER,object_id INTEGER,can_view_dashboard INTEGER,can_view_selection INTEGER);
            INSERT INTO users VALUES(1,'admin'),(2,'viewer'),(3,'manager');
            INSERT INTO objects_settings VALUES(1,'Первый'),(2,'Второй');
            INSERT INTO user_module_permissions VALUES(2,'selection',1);
            INSERT INTO user_object_permissions VALUES(2,1,0,1);
        ''')

    def department(self, policy='{"modules":{"selection":true},"objects":{"2":true}}'):
        migrate(self.db)
        self.db.execute('INSERT INTO access_departments VALUES(1,?,?)', ('Подбор', policy))

    def test_missing_migration_and_unassigned_preserve_legacy(self):
        self.assertIsNone(effective(self.db, 2))
        migrate(self.db)
        migrate(self.db)
        self.assertIsNone(effective(self.db, 2))
        self.assertEqual(self.db.execute('SELECT can_view FROM user_module_permissions').fetchone()[0], 1)

    def test_inherit(self):
        self.department()
        assign(self.db, [2], 1, 'inherit')
        modules, objects = effective(self.db, 2)
        self.assertTrue(modules['selection'])
        self.assertFalse(modules['reports'])
        self.assertFalse(objects[1]['selection'])
        self.assertTrue(objects[2]['selection'])

    def test_preserve(self):
        self.department()
        assign(self.db, [2,3], 1, 'preserve')
        modules, objects = effective(self.db, 2)
        self.assertTrue(objects[1]['selection'])
        self.assertFalse(objects[1]['dashboard'])
        self.assertFalse(objects[2]['selection'])
        self.assertTrue(effective(self.db, 3)[0]['admin'])
        self.assertFalse(modules['admin'])

    def test_explicit_deny_and_allow(self):
        self.department()
        assign(self.db, [2], 1, 'inherit')
        self.db.execute('UPDATE access_memberships SET overrides=? WHERE user_id=2', ('{"modules":{"selection":false,"reports":true},"objects":{"1":true,"2":false}}',))
        modules, objects = effective(self.db, 2)
        self.assertFalse(modules['selection'])
        self.assertTrue(modules['reports'])
        self.assertTrue(objects[1]['selection'])
        self.assertFalse(objects[2]['selection'])

    def test_all_includes_future_objects(self):
        self.department('{"modules":{},"objects":{},"all_objects":true}')
        assign(self.db, [2], 1, 'inherit')
        self.db.execute("INSERT INTO objects_settings VALUES(3,'Новый')")
        self.assertTrue(effective(self.db, 2)[1][3]['selection'])

    def test_bulk_validation_before_any_write(self):
        self.department()
        with self.assertRaises(ValueError):
            assign(self.db, [2,1], 1, 'inherit')
        self.assertIsNone(effective(self.db, 2))

    def test_only_one_department_and_reset(self):
        self.department()
        self.db.execute('INSERT INTO access_departments VALUES(2,?,?)', ('Другой', '{"modules":{},"objects":{}}'))
        assign(self.db, [2], 1, 'preserve')
        assign(self.db, [2], 2, 'inherit')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM access_memberships').fetchone()[0], 1)
        self.assertFalse(effective(self.db, 2)[0]['selection'])

    def test_changes_propagate(self):
        self.department()
        assign(self.db, [2], 1, 'inherit')
        self.db.execute('UPDATE access_departments SET policy=?', ('{"modules":{"reports":true},"objects":{}}',))
        self.assertTrue(effective(self.db, 2)[0]['reports'])
        self.assertFalse(effective(self.db, 2)[0]['selection'])

    def test_reject_string_booleans(self):
        with self.assertRaises(ValueError):
            validate_policy({'modules': {'reports': 'false'}})
        with self.assertRaises(ValueError):
            validate_policy({'objects': {'1': 1}})

    def test_model_uses_policy_and_blocks_object_when_module_denied(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'models.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'User')
        namespace = {'UserMixin': object, 'logger': logging.getLogger('test')}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'models.py', 'exec'), namespace)
        user = namespace['User']({'id':2,'username':'test','password_hash':'','role':'viewer'})
        with patch('access_policy.get_effective', return_value=({'selection':False,'reports':True,'admin':False}, {1:{'selection':True}})):
            self.assertFalse(user.can_view_object(1))
            self.assertTrue(user.can_view_reports())
            self.assertFalse(user.can_view_admin())

    def test_admin_guard_does_not_block_selection_documents(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'app.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'department_admin_gate')
        node.decorator_list = []
        request = SimpleNamespace(path='/admin', blueprint=None, method='GET')
        namespace = {'request':request, 'jsonify':lambda **kw: kw}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'app.py', 'exec'), namespace)
        user = SimpleNamespace(is_authenticated=True, can_view_admin=lambda:False)
        with patch.dict('sys.modules', {'flask_login':SimpleNamespace(current_user=user)}):
            self.assertEqual(namespace['department_admin_gate']()[1], 403)
            request.path = '/api/admin/users'
            request.blueprint = 'admin'
            self.assertEqual(namespace['department_admin_gate']()[1], 403)
            request.path = '/api/admin/objects/1/passport'
            request.blueprint = 'objects_admin'
            self.assertIsNone(namespace['department_admin_gate']())
            request.method = 'POST'
            self.assertEqual(namespace['department_admin_gate']()[1], 403)


if __name__ == '__main__':
    unittest.main()
