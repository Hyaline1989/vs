"""Проверка распределения сделок по офисам без запросов в Битрикс24."""
import ast
from datetime import datetime
import logging
from pathlib import Path
import re
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'bitrix_api.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
CLASS = next(node for node in TREE.body
             if isinstance(node, ast.ClassDef) and node.name == 'BitrixAPI')
NAMESPACE = {
    'datetime': datetime,
    're': re,
    'logger': logging.getLogger('test_dashboard_office_prefix'),
    'FIELD_DATE_DIRECTED': 'DATE',
    'FIELD_COMPANY': 'COMPANY',
    'FIELD_CC_OPERATOR_REPORT': 'STAFF',
    'SOURCE_AGENT': 'AGENT',
    'SOURCE_BISHKEK': 'BISHKEK',
    'SOURCE_POTOK': 'OLD_POTOK',
    'SOURCE_GORKIY52': 'GORKIY',
    'EXCLUDED_SOURCES': ['EXCLUDED'],
    'is_operator': lambda name: False,
}
exec(compile(ast.Module(body=[CLASS], type_ignores=[]), str(SOURCE), 'exec'), NAMESPACE)


class DashboardOfficePrefixTests(unittest.TestCase):
    def test_new_source_uses_potok_staff_prefix(self):
        api = object.__new__(NAMESPACE['BitrixAPI'])
        deals = [
            {'SOURCE_ID': 'UC_RPXAT4', 'STAFF': 'Поток Иванова',
             'DATE': '2026-10-15', 'COMPANY': '1'},
            {'SOURCE_ID': 'UC_RPXAT4', 'STAFF': 'Комплект Петрова',
             'DATE': '2026-10-15', 'COMPANY': '1'},
            {'SOURCE_ID': 'AGENT', 'STAFF': 'Поток Агент',
             'DATE': '2026-10-15', 'COMPANY': '1'},
            {'SOURCE_ID': 'BISHKEK', 'STAFF': 'Поток Бишкек',
             'DATE': '2026-10-15', 'COMPANY': '1'},
            {'SOURCE_ID': 'OLD_POTOK', 'STAFF': 'Сотрудник',
             'DATE': '2026-10-15', 'COMPANY': '1'},
            {'SOURCE_ID': 'EXCLUDED', 'STAFF': 'Поток Исключен',
             'DATE': '2026-10-15', 'COMPANY': '1'},
        ]
        api._get_all_deals_raw = lambda filters: deals
        api._get_companies_info = lambda ids: {'1': 'Объект'}
        result = api.get_report_facts_range('2026-10-15', '2026-10-15', True)
        counts = result['facts']['2026-10-15']['Объект']
        self.assertEqual(counts, {
            'complect': 1, 'potok': 2, 'gorkiy': 0,
            'agent': 1, 'bishkek': 1,
        })
        self.assertEqual(sum(counts.values()), 5)
        self.assertEqual(result['staff']['2026-10-15']['Объект']['Поток Иванова'], 1)

        # Фиксация дня и фоновые дневные снимки берут те же цифры.
        offices = api.get_all_offices_stats('2026-10-15')
        self.assertEqual(offices['potok']['objects']['Объект'], 2)
        self.assertEqual(offices['complect']['objects']['Объект'], 1)
        self.assertEqual(sum(office['count'] for office in offices.values()), 5)


if __name__ == '__main__':
    unittest.main()
