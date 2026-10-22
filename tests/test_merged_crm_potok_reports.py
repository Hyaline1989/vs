"""Распределение Потока после объединения CRM и UIS."""
import unittest

from bitrix_api import ShiftReportAPI
from config import (
    FIELD_AGENT_FIO, FIELD_CC_OPERATOR_REPORT, FIELD_DATE_DIRECTED,
    SOURCE_BISHKEK, SOURCE_POTOK,
)
from manager_results import build_manager_results


class MergedCrmPotokReportsTests(unittest.TestCase):
    def test_first_shift_staff_uses_prefix_when_source_is_shared(self):
        api = ShiftReportAPI('https://example.invalid/')
        deals = [
            {'SOURCE_ID': 'UC_RPXAT4', FIELD_CC_OPERATOR_REPORT: 'Поток Иванов Иван'},
            {'SOURCE_ID': SOURCE_POTOK, FIELD_CC_OPERATOR_REPORT: 'Иванов Иван'},
            {'SOURCE_ID': 'UC_RPXAT4', FIELD_CC_OPERATOR_REPORT: 'Комплект Петрова Анна'},
            {'SOURCE_ID': 'UC_RPXAT4', FIELD_CC_OPERATOR_REPORT: 'Сервис Смирнова Елена'},
            {'SOURCE_ID': SOURCE_BISHKEK, FIELD_CC_OPERATOR_REPORT: 'Бишкек Алиева'},
        ]
        result = api._group_by_staff(deals)
        self.assertEqual(result['Поток']['Поток Иванов Иван'], 1)
        self.assertEqual(result['Поток']['Иванов Иван'], 1)
        self.assertEqual(result['Комплект']['Комплект Петрова Анна'], 1)
        self.assertEqual(result['Сервис']['Сервис Смирнова Елена'], 1)
        self.assertEqual(result['Бишкек']['Бишкек Алиева'], 1)

    def test_manager_results_matches_potok_calls_and_deals(self):
        calls = [
            {'system': 'Комплект', 'employee_name': '(bitrix24) Поток Иванов Иван',
             'count': 10},
            {'system': 'Комплект', 'employee_name': 'Комплект Петрова Анна',
             'count': 8},
        ]
        deals = [
            {'SOURCE_ID': 'UC_RPXAT4', FIELD_CC_OPERATOR_REPORT: 'Поток Иванов Иван',
             FIELD_DATE_DIRECTED: '2026-10-15', FIELD_AGENT_FIO: ''},
            {'SOURCE_ID': 'UC_RPXAT4', FIELD_CC_OPERATOR_REPORT: 'Комплект Петрова Анна',
             FIELD_DATE_DIRECTED: '2026-10-15', FIELD_AGENT_FIO: ''},
        ]
        rows, totals = build_manager_results(calls, deals)
        by_system = {row['system']: row for row in rows}
        self.assertEqual(by_system['Поток']['calls'], 10)
        self.assertEqual(by_system['Поток']['directed'], 1)
        self.assertEqual(by_system['Комплект']['calls'], 8)
        self.assertEqual(by_system['Комплект']['directed'], 1)
        self.assertEqual(totals['directed'], 2)


if __name__ == '__main__':
    unittest.main()
