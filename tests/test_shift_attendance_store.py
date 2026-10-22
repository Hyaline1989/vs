import tempfile
import unittest
from datetime import date
from pathlib import Path

from shift_attendance_store import read_snapshot, report_for_period, validate_snapshot, write_snapshot


class ShiftAttendanceStoreTests(unittest.TestCase):
    def test_empty_day_is_zero_and_missing_sheet_is_unknown(self):
        snapshot = validate_snapshot({
            'month': '2026-10',
            'objects': [
                {'name': 'Б', 'counts': [0] + [None] * 30,
                 'reasons': [None] + ['sheet_missing'] * 30},
                {'name': 'А', 'counts': [2] * 31},
            ],
        })
        self.assertEqual([row['name'] for row in snapshot['objects']], ['А', 'Б'])
        self.assertEqual(snapshot['objects'][1]['counts'][0], 0)
        self.assertIsNone(snapshot['objects'][1]['counts'][1])

    def test_rejects_ambiguous_values(self):
        with self.assertRaises(ValueError):
            validate_snapshot({'month': '2026-10', 'objects': [
                {'name': 'А', 'counts': [None] + [0] * 30}]})
        with self.assertRaises(ValueError):
            validate_snapshot({'month': '2026-10', 'objects': [
                {'name': 'А', 'counts': [True] + [0] * 30}]})

    def test_snapshot_round_trip(self):
        snapshot = validate_snapshot({'month': '2026-10', 'objects': [
            {'name': 'А', 'counts': [0] * 31}]})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            write_snapshot(snapshot, directory)
            self.assertEqual(read_snapshot('2026-10', directory), snapshot)

    def test_period_spans_months_and_marks_missing_data(self):
        september = validate_snapshot({'month': '2026-09', 'objects': [
            {'name': 'А', 'counts': [0] * 29 + [2]},
            {'name': 'Б', 'counts': [1] * 30},
        ]})
        october = validate_snapshot({'month': '2026-10', 'objects': [
            {'name': 'А', 'counts': [3] + [0] * 30},
            {'name': 'Б', 'counts': [None] + [0] * 30,
             'reasons': ['source_unavailable'] + [None] * 30},
        ]})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            write_snapshot(september, directory)
            write_snapshot(october, directory)
            report = report_for_period(date(2026, 9, 30), date(2026, 10, 1), directory)
        self.assertEqual(report['dates'], ['2026-09-30', '2026-10-01'])
        self.assertEqual(report['totals'], [3, 3])
        self.assertEqual(report['incomplete'], [False, True])
        self.assertEqual(report['objects'][0]['counts'], [2, 3])

    def test_unloaded_month_is_not_zero(self):
        august = validate_snapshot({'month': '2026-08', 'objects': [
            {'name': 'А', 'counts': [0] * 31}]})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            write_snapshot(august, directory)
            report = report_for_period(date(2026, 8, 31), date(2026, 9, 1), directory)
        self.assertEqual(report['objects'][0]['counts'], [0, None])
        self.assertEqual(report['objects'][0]['reasons'], [None, 'month_not_loaded'])
        self.assertEqual(report['totals'], [0, None])


if __name__ == '__main__':
    unittest.main()
