"""Проверки отчёта «В пути» без обращения к рабочим данным."""
import unittest
from unittest.mock import MagicMock

from test_shift_report_loading import make_api


class InTransitReportTests(unittest.TestCase):
    def make_report_api(self, payloads):
        api, session = make_api(payloads)
        api.get_object_stage_report.__globals__.update(
            CHECK_IN_FIELD='CHECK_IN_FIELD', IN_TRANSIT_STAGE_ID='3',
            Retry=MagicMock(), HTTPAdapter=MagicMock(),
        )
        api._group_by_companies = MagicMock(return_value=({}, {}))
        return api, session

    def test_current_stage_without_date_filter_on_every_page(self):
        first = {'ID': '1', 'STAGE_ID': '3', 'FIELD_DATE_DIRECTED': '2026-10-01'}
        second = {'ID': '2', 'STAGE_ID': 3}
        other = {'ID': '3', 'STAGE_ID': '4', 'FIELD_DATE_DIRECTED': '2026-10-02'}
        api, session = self.make_report_api([
            {'result': [first], 'next': 50}, {'result': [second, other]},
        ])
        api.get_object_stage_report('in_transit', '2026-10-01', '2026-10-07')
        for call in session.post.call_args_list:
            self.assertEqual(call.kwargs['json']['filter'], {
                'STAGE_ID': '3',
            })
        self.assertEqual(session.post.call_args_list[1].kwargs['json']['start'], 50)
        api._group_by_companies.assert_called_once_with([first, second], include_staff=True)

    def test_existing_reports_do_not_filter_current_stage(self):
        for stage, field in [('directed', 'FIELD_DATE_DIRECTED'),
                             ('checked_in', 'CHECK_IN_FIELD')]:
            with self.subTest(stage=stage):
                deal = {'ID': '1', 'STAGE_ID': 'WON', field: '2026-10-01'}
                api, session = self.make_report_api([{'result': [deal]}])
                api.get_object_stage_report(stage, '2026-10-01', '2026-10-07')
                self.assertNotIn('STAGE_ID', session.post.call_args.kwargs['json']['filter'])
                api._group_by_companies.assert_called_once_with([deal], include_staff=True)

    def test_api_error_does_not_return_partial_report(self):
        api, _ = self.make_report_api([{'error': 'QUERY_LIMIT_EXCEEDED'}])
        with self.assertRaises(RuntimeError):
            api.get_object_stage_report('in_transit', '2026-10-01', '2026-10-07')
        api._group_by_companies.assert_not_called()
