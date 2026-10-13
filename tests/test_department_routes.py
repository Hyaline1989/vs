"""Test only the isolated department blueprint, never the production app."""
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from flask import Flask
from access_policy import migrate


class DepartmentRouteTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = str(Path(temp.name) / 'test.db')
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.executescript('''
                CREATE TABLE users(id INTEGER PRIMARY KEY,role TEXT,full_name TEXT,username TEXT);
                CREATE TABLE objects_settings(id INTEGER PRIMARY KEY,name TEXT);
                CREATE TABLE user_module_permissions(user_id INTEGER,module_name TEXT,can_view INTEGER,UNIQUE(user_id,module_name));
                CREATE TABLE user_object_permissions(user_id INTEGER,object_id INTEGER,can_view_dashboard INTEGER,can_view_selection INTEGER,UNIQUE(user_id,object_id));
                INSERT INTO users VALUES(1,'admin','Admin','admin'),(2,'viewer','User','user');
                INSERT INTO objects_settings VALUES(1,'Object');
                INSERT INTO user_module_permissions VALUES(2,'selection',1);
                INSERT INTO user_object_permissions VALUES(2,1,0,1);
            ''')
            migrate(conn)
        fake = ModuleType('database.db_core')
        fake.DB_NAME = self.path
        spec = importlib.util.spec_from_file_location('isolated_departments', Path(__file__).resolve().parents[1] / 'routes/departments.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'database':ModuleType('database'), 'database.db_core':fake}):
            spec.loader.exec_module(self.module)
        self.module.current_user = SimpleNamespace(is_authenticated=True, role='admin')
        app = Flask('department_tests')
        app.config['TESTING'] = True
        app.register_blueprint(self.module.departments_bp)
        self.client = app.test_client()

    def test_create_assign_and_override(self):
        r = self.client.post('/api/departments', json={'name':'Test','modules':{'selection':True},'objects':{'1':True}})
        self.assertEqual(r.status_code, 200)
        did = r.json['id']
        r = self.client.post('/api/departments/assign', json={'department_id':did,'user_ids':[2],'mode':'preserve'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.client.get('/api/departments/users/2').json['effective'][0]['selection'])
        r = self.client.put('/api/departments/users/2', json={'modules':{'selection':False},'objects':{}})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json['effective'][0]['selection'])

    def test_legacy_rights_visible_and_unchanged_until_saved(self):
        before = self.client.get('/api/departments/users/2').json
        self.assertTrue(before['legacy'])
        self.assertIsNone(before['overrides'])
        self.assertTrue(before['effective'][0]['selection'])
        self.assertTrue(before['effective'][1]['1']['selection'])
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertIsNone(conn.execute('SELECT user_id FROM access_memberships WHERE user_id=2').fetchone())
        after = self.client.get('/api/departments/users/2').json
        self.assertEqual(after, before)

    def test_legacy_edit_stays_in_legacy_tables(self):
        body = {'modules': {'dashboard': False, 'selection': True, 'worker_status': False,
                            'reports': True, 'admin': False}, 'objects': {'1': False}}
        response = self.client.put('/api/departments/users/2', json=body)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['legacy'])
        self.assertTrue(response.json['effective'][0]['reports'])
        self.assertFalse(response.json['effective'][1]['1']['selection'])
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertIsNone(conn.execute('SELECT user_id FROM access_memberships WHERE user_id=2').fetchone())
            self.assertEqual(conn.execute('SELECT can_view_dashboard FROM user_object_permissions WHERE user_id=2 AND object_id=1').fetchone()[0], 0)

    def test_unassigned_employee_immediately_inherits_department(self):
        did = self.client.post('/api/departments', json={'name':'Restricted','modules':{},'objects':{}}).json['id']
        response = self.client.post('/api/departments/assign', json={'department_id':did,'user_ids':[2],'mode':'inherit'})
        self.assertEqual(response.status_code, 200)
        after = self.client.get('/api/departments/users/2').json
        self.assertFalse(after['legacy'])
        self.assertFalse(after['effective'][0]['selection'])
        self.assertFalse(after['effective'][1]['1']['selection'])
        self.assertEqual(after['overrides'], {'modules': {}, 'objects': {}, 'dashboard_objects': {}})

    def test_mixed_assignment_only_changes_unassigned_users_rights(self):
        narrow = self.client.post('/api/departments', json={'name':'Restricted','modules':{},'objects':{}}).json['id']
        broad = self.client.post('/api/departments', json={'name':'Broad','modules':{'selection':True},'objects':{'1':True}}).json['id']
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("INSERT INTO users VALUES(3,'viewer','Other','other')")
            conn.execute("INSERT INTO user_module_permissions VALUES(3,'reports',1)")
        self.assertEqual(self.client.post('/api/departments/assign', json={'department_id':broad,'user_ids':[2]}).status_code, 200)
        before = self.client.get('/api/departments/users/2').json['effective']
        self.assertEqual(self.client.post('/api/departments/assign', json={'department_id':narrow,'user_ids':[2,3]}).status_code, 200)
        self.assertEqual(self.client.get('/api/departments/users/2').json['effective'], before)
        self.assertFalse(self.client.get('/api/departments/users/3').json['effective'][0]['reports'])
        self.assertEqual(self.client.get('/api/departments/users/3').json['overrides']['modules'], {})

    def test_apply_requires_preview_and_reports_changes(self):
        did = self.client.post('/api/departments', json={'name':'Restricted','modules':{},'objects':{}}).json['id']
        self.client.post('/api/departments/assign', json={'department_id':did,'user_ids':[2]})
        self.client.put('/api/departments/users/2', json={'modules':{'selection':True},'objects':{}})
        preview = self.client.post('/api/departments/assignment-preview', json={'user_id':2,'department_id':did}).json
        self.assertIn('selection', preview['changes']['modules'])
        self.assertEqual(self.client.post('/api/departments/apply-department', json={'user_id':2,'department_id':did,'token':'wrong'}).status_code, 400)
        self.assertTrue(self.client.get('/api/departments/users/2').json['effective'][0]['selection'])
        self.assertEqual(self.client.post('/api/departments/apply-department', json={'user_id':2,'department_id':did,'token':preview['token']}).status_code, 200)
        self.assertFalse(self.client.get('/api/departments/users/2').json['effective'][0]['selection'])

    def test_non_admin_and_anonymous_denied(self):
        for role in ('manager','viewer'):
            self.module.current_user = SimpleNamespace(is_authenticated=True, role=role)
            self.assertEqual(self.client.get('/api/departments').status_code, 403)
            self.assertEqual(self.client.post('/api/departments', json={'name':'Test'}).status_code, 403)
        self.module.current_user = SimpleNamespace(is_authenticated=False)
        self.assertEqual(self.client.get('/api/departments').status_code, 401)

    def test_transfer_preserves_access_even_from_old_ui(self):
        narrow = self.client.post('/api/departments', json={'name':'Test','modules':{'selection':True}}).json['id']
        broad = self.client.post('/api/departments', json={'name':'Managers','modules':{'reports':True,'admin':True},'all_objects':True}).json['id']
        for did in (narrow, broad):
            self.assertEqual(self.client.post('/api/departments/assign', json={'department_id':did,'user_ids':[2]}).status_code, 200)
        self.assertFalse(self.client.get('/api/departments/users/2').json['effective'][0]['reports'])
        self.client.put('/api/departments/users/2', json={'modules':{'dashboard':True},'objects':{'1':True}})
        response = self.client.post('/api/departments/assign', json={'department_id':narrow,'user_ids':[2],'mode':'preserve'})
        self.assertEqual(response.status_code, 200)
        result = self.client.get('/api/departments/users/2').json
        self.assertEqual(result['effective'][0]['dashboard'], True)
        self.assertEqual(result['effective'][1]['1']['selection'], True)

    def test_remove_preserves_permissions_and_account(self):
        did = self.client.post('/api/departments', json={'name':'Test','modules':{'selection':True,'reports':True},'all_objects':True}).json['id']
        self.client.post('/api/departments/assign', json={'department_id':did,'user_ids':[2],'mode':'preserve'})
        self.client.put('/api/departments/users/2', json={'modules':{'reports':False},'objects':{}})
        before = self.client.get('/api/departments/users/2').json['effective']
        response = self.client.post('/api/departments/assign', json={'department_id':None,'user_ids':[2],'mode':'preserve'})
        self.assertEqual(response.status_code, 200)
        after = self.client.get('/api/departments/users/2').json
        self.assertIsNone(after['department_id'])
        self.assertEqual(before, after['effective'])
        self.client.put('/api/departments/' + str(did), json={'name':'Test','modules':{},'objects':{}})
        self.assertEqual(before, self.client.get('/api/departments/users/2').json['effective'])
        users = self.client.get('/api/departments').json['users']
        self.assertEqual(users[0]['id'], 2)
        self.assertIsNone(users[0]['department_id'])

    def test_no_schema_is_explicit_error(self):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('DROP TABLE access_memberships')
        self.assertEqual(self.client.get('/api/departments').status_code, 409)

    def test_invalid_and_duplicate_names(self):
        self.assertEqual(self.client.post('/api/departments', json={'name':' '}).status_code, 400)
        self.assertEqual(self.client.post('/api/departments', json={'name':'Test'}).status_code, 200)
        self.assertEqual(self.client.post('/api/departments', json={'name':'Test'}).status_code, 409)

    def test_cross_origin_mutation_denied(self):
        self.assertEqual(self.client.post('/api/departments', json={'name':'Test'}, headers={'Origin':'https://other.example'}).status_code, 403)


if __name__ == '__main__':
    unittest.main()
