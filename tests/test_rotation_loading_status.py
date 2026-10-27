import unittest
from unittest.mock import patch
from rotation_duration import saved_loading_status


class LoadingStatusTests(unittest.TestCase):
    def snapshot(self):
        return {'updated_at': '2026-10-27T08:00:00+00:00',
                'objects': [{'name': 'A', 'reason': 'sheet_missing'}, {'name': 'B'}]}

    @patch('rotation_duration._read', return_value=None)
    def test_all_saved_including_source_warning(self, _):
        result = saved_loading_status(['2026-07', '2026-08'],
            {'2026-07': self.snapshot(), '2026-08': self.snapshot()})
        self.assertTrue(result['complete'])
        self.assertEqual(result['parts_saved'], 4)
        self.assertEqual(result['parts_total'], 4)

    @patch('rotation_duration._read', return_value=None)
    def test_missing_month_does_not_invent_total(self, _):
        result = saved_loading_status(['2026-07', '2026-08'],
            {'2026-07': self.snapshot(), '2026-08': None})
        self.assertFalse(result['complete'])
        self.assertEqual(result['months_saved'], 1)
        self.assertIsNone(result['parts_total'])

    def test_new_refresh_does_not_look_finished(self):
        for status in ['pending', 'error']:
            with patch('rotation_duration._read', return_value={
                    'requested_at': '2026-10-27T09:00:00+00:00', 'status': status}):
                result = saved_loading_status(['2026-07'], {'2026-07': self.snapshot()})
                self.assertEqual(result['months'][0]['refresh_status'], status)
                self.assertTrue(result['complete'])  # Only the OLD saved data is complete.

    @patch('rotation_duration._read', return_value={
        'requested_at': '2026-10-27T07:00:00+00:00', 'status': 'completed'})
    def test_completed_request(self, _):
        result = saved_loading_status(['2026-07'], {'2026-07': self.snapshot()})
        self.assertIsNone(result['months'][0]['refresh_status'])


if __name__ == '__main__':
    unittest.main()
