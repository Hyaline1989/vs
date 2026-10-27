"""Проверки на обезличенном примере UIS, без сети и настроек приложения."""
import ast
from collections import defaultdict
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_functions(filename, names, namespace):
    tree = ast.parse((ROOT / filename).read_text(encoding='utf-8-sig'))
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=selected, type_ignores=[]), filename, 'exec'), namespace)


tree = ast.parse((ROOT / 'uis_api.py').read_text(encoding='utf-8-sig'))
klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'UISAPI')
klass.body = [n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name in
              ('_normalize_calls', '_normalize_call_row', '_normalize_datetime')]
ns = {}
exec(compile(ast.Module(body=[klass], type_ignores=[]), 'uis_api.py', 'exec'), ns)


class CallAttributionTests(unittest.TestCase):
    def setUp(self):
        self.api = ns['UISAPI']()
        self.call = dict(id=1, direction='out', clean_talk_duration=18,
                         start_time='2026-10-25 15:54:11', finish_time='2026-10-25 15:54:46',
                         employees=[dict(employee_full_name='Опер Получатель', is_talked=False),
                                    dict(employee_full_name='Сервис Звонивший', is_talked=True)])

    def test_success_only_for_talking_employee(self):
        rows = self.api._normalize_calls('Комплект', [self.call])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['employee_name'], 'Сервис Звонивший')
        self.assertEqual(rows[0]['clean_talk_duration'], 18)

    def test_failed_attempts_preserved(self):
        self.call['clean_talk_duration'] = 0
        self.assertEqual(len(self.api._normalize_calls('Комплект', [self.call])), 2)

    def test_incoming_unchanged(self):
        self.call['direction'] = 'in'
        self.assertEqual(len(self.api._normalize_calls('Комплект', [self.call])), 2)

    def test_cache_cannot_reintroduce_non_talking_employee(self):
        scope = dict(defaultdict=defaultdict, re=re,
                     EXCLUDED_MANAGER_PREFIXES=['сервис', 'без менеджера'],
                     EXCLUDED_MANAGER_NAME_PARTS=[], SHORT_CALL_SECONDS=15)
        load_functions('manager_efficiency.py', {'is_excluded_manager', 'calculate_efficiency_rating'}, scope)
        old_rows = [self.api._normalize_call_row('Комплект', self.call, e) for e in self.call['employees']]
        self.assertEqual(scope['calculate_efficiency_rating'](old_rows), [])

    def test_employee_with_successful_call_is_kept(self):
        self.call['employees'] = [dict(employee_full_name='Менеджер', is_talked=True)]
        self.assertEqual(len(self.api._normalize_calls('Комплект', [self.call])), 1)


if __name__ == '__main__':
    unittest.main()
