"""Проверки изменения роли без запуска приложения и записи в БД."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock


class UserRoleChangeTests(unittest.TestCase):
    def test_create_rejected_after_demotion_before_reading_payload(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'routes/admin.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'create_user_api')
        node.decorator_list = []
        for role in ('manager', 'viewer', 'agent'):
            request = MagicMock()
            create = MagicMock()
            ns = dict(current_user=SimpleNamespace(is_authenticated=True, role=role),
                      request=request, jsonify=lambda data: data, create_user=create)
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<test>', 'exec'), ns)
            self.assertEqual(ns['create_user_api']()[1], 403)
            request.get_json.assert_not_called()
            create.assert_not_called()

    def invoke(self, actor, target, role, target_role='admin', saved=True):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'routes/admin.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'update_user_api')
        node.decorator_list = []
        ns = dict(current_user=SimpleNamespace(id=actor, role='admin' if actor in (1, 2) else 'manager', is_authenticated=True),
                  request=SimpleNamespace(get_json=lambda: {'role': role}, remote_addr='test'),
                  jsonify=lambda data: data, get_user_by_id=lambda _: {'role': target_role},
                  is_system_admin=lambda uid: uid == 1, update_user=MagicMock(return_value=saved),
                  log_user_action=MagicMock())
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<test>', 'exec'), ns)
        return ns['update_user_api'](target), ns

    def test_all_supported_transitions(self):
        for old in ('admin', 'manager', 'viewer', 'agent'):
            for new in ('admin', 'manager', 'viewer', 'agent'):
                result, ns = self.invoke(1, 7, new, old)
                self.assertEqual(result, {'success': True})
                ns['update_user'].assert_called_once_with(7, {'role': new})

    def test_other_roles_cannot_change_role(self):
        for actor in (2, 3):
            result, ns = self.invoke(actor, 7, 'admin')
            self.assertEqual(result[1], 403)
            ns['update_user'].assert_not_called()

    def test_self_protected_and_invalid_role_rejected(self):
        for target, role, status in [(1, 'viewer', 403), (7, 'system_admin', 400)]:
            result, ns = self.invoke(1, target, role)
            self.assertEqual(result[1], status)
            ns['update_user'].assert_not_called()

    def test_save_failure_is_reported(self):
        result, ns = self.invoke(1, 7, 'viewer', saved=False)
        self.assertEqual(result[1], 500)
        ns['log_user_action'].assert_not_called()

    def test_manager_sees_and_can_read_agent_permissions(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'routes/admin.py').read_text(encoding='utf-8'))
        user = {'id': 7, 'role': 'agent'}
        manager = SimpleNamespace(id=3, role='manager', is_authenticated=True)
        ns = dict(current_user=manager, jsonify=lambda data: data,
                  get_all_users=lambda: [user, {'id': 8, 'role': 'viewer'}, {'id': 9, 'role': 'admin'}],
                  get_user_by_id=lambda _: user,
                  get_user_module_permissions=lambda _: {'selection': True})
        for name in ('get_users', 'get_user_module_perms'):
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            node.decorator_list = []
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<test>', 'exec'), ns)
        self.assertEqual([item['role'] for item in ns['get_users']()], ['agent', 'viewer'])
        self.assertEqual(ns['get_user_module_perms'](7), {'selection': True})
