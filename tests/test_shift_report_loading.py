"""Изолированные тесты загрузки: без Flask, базы и настоящего Битрикс24."""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock


def make_api(payloads):
    # Загружаем только класс, исключая настройки и побочные эффекты приложения.
    source = Path(__file__).resolve().parents[1] / 'bitrix_api.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ShiftReportAPI')
    session = MagicMock()
    session.__enter__.return_value = session
    responses = []
    for payload in payloads:
        response = MagicMock()
        response.json.return_value = payload
        responses.append(response)
    session.post.side_effect = responses
    namespace = {
        'BITRIX_WEBHOOK_URL': 'https://example.invalid/',
        'logger': logging.getLogger('test'),
        'monotonic': lambda: 0,
        'requests': SimpleNamespace(Session=lambda: session,
                                    exceptions=SimpleNamespace(RequestException=OSError)),
    }
    for name in ('FIELD_DATE_DIRECTED', 'FIELD_COMPANY', 'FIELD_CC_OPERATOR',
                 'FIELD_CC_OPERATOR_REPORT', 'FIELD_WORKED_1_SHIFT', 'FIELD_AGENT_FIO',
                 'SOURCE_AGENT'):
        namespace[name] = name
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['ShiftReportAPI'](), session


class ShiftReportLoadingTests(unittest.TestCase):
    def test_pagination_preserves_period_and_all_deals(self):
        api, session = make_api([
            {'result': [{'ID': str(i)} for i in range(1, 51)]},
            {'result': [{'ID': '51'}]},
        ])
        result = api._get_deals_by_date('2026-09-01', '2026-09-29')
        self.assertEqual(len(result), 51)
        params = session.post.call_args_list[1].kwargs['json']
        self.assertEqual(params['filter'], {
            '>=FIELD_DATE_DIRECTED': '2026-09-01',
            '<=FIELD_DATE_DIRECTED': '2026-09-29', '>ID': 50,
        })
        self.assertEqual(params['start'], -1)
        self.assertEqual(params['order'], {'ID': 'ASC'})

    def test_error_on_later_page_does_not_return_partial_report(self):
        api, _ = make_api([
            {'result': [{'ID': str(i)} for i in range(1, 51)]},
            {'error': 'QUERY_LIMIT_EXCEEDED'},
        ])
        with self.assertRaises(RuntimeError):
            api._get_deals_by_date('2026-09-01', '2026-09-29')

    def test_repeated_page_is_rejected(self):
        page = {'result': [{'ID': str(i)} for i in range(1, 51)]}
        api, _ = make_api([page, page])
        with self.assertRaises(RuntimeError):
            api._get_deals_by_date('2026-09-01', '2026-09-29')

    def test_company_batches_and_id_types(self):
        api, session = make_api([
            {'result': [{'ID': str(i), 'TITLE': str(i)} for i in range(1, 51)]},
            {'result': [{'ID': '51', 'TITLE': '51'}]},
        ])
        result = api._get_companies_info(list(range(1, 51)) + ['51', 1])
        self.assertEqual(result[1], '1')
        self.assertEqual(result['51'], '51')
        self.assertEqual(session.post.call_count, 2)
        self.assertTrue(all(c.args[0].endswith('crm.company.list')
                            for c in session.post.call_args_list))

    def test_group_totals_and_shift_filter_unchanged(self):
        deals = [
            {'ID': '1', 'FIELD_COMPANY': '10', 'FIELD_WORKED_1_SHIFT': '2026-09-30'},
            {'ID': '2', 'FIELD_COMPANY': 10, 'FIELD_WORKED_1_SHIFT': '2026-09-02',
             'FIELD_AGENT_FIO': 'Агент'},
            {'ID': '3', 'FIELD_COMPANY': '10', 'FIELD_WORKED_1_SHIFT': '2026-09-03',
             'FIELD_CC_OPERATOR_REPORT': 'Спутник Иван'},
            {'ID': '4', 'FIELD_COMPANY': '10', 'FIELD_WORKED_1_SHIFT': 'N'},
            {'ID': '5', 'FIELD_COMPANY': '10'},
        ]
        api, _ = make_api([{'result': deals}, {'result': [{'ID': '10', 'TITLE': 'Объект'}]}])
        self.assertEqual(api.get_shift_report('2026-09-01', '2026-09-29'), {
            'Основной': {'Объект': 1}, 'Агенты': {'Объект': 1},
            'Опер и Спутник': {'Объект': 1},
        })

    def test_deadline_prevents_new_request(self):
        api, session = make_api([])
        api._report_deadline = -1
        with self.assertRaises(RuntimeError):
            api._report_request(session, 'crm.deal.list', {})
        session.post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
