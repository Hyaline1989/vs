import tempfile
import unittest
from pathlib import Path

from planned_departures_store import (
    read_snapshot, totals_for, validate_snapshot, write_snapshot,
)


class PlannedDeparturesStoreTests(unittest.TestCase):
    def test_unknown_day_is_not_zero(self):
        snapshot = validate_snapshot({
            'month': '2026-10',
            'objects': [
                {'name': 'Б', 'counts': [2] * 30 + [None]},
                {'name': 'А', 'counts': [1] * 31},
            ],
        })
        self.assertEqual([row['name'] for row in snapshot['objects']], ['А', 'Б'])
        self.assertEqual(totals_for(snapshot), [3] * 30 + [None])

    def test_rejects_duplicate_object_and_invalid_count(self):
        base = {'month': '2026-10', 'objects': [{'name': 'А', 'counts': [0] * 31}]}
        with self.assertRaises(ValueError):
            validate_snapshot({**base, 'objects': base['objects'] * 2})
        with self.assertRaises(ValueError):
            validate_snapshot({**base, 'objects': [{'name': 'А', 'counts': [True] * 31}]})

    def test_snapshot_round_trip(self):
        snapshot = validate_snapshot({
            'month': '2026-10',
            'objects': [{
                'name': 'Форум Авто', 'counts': [None] + [0] * 30,
                'reasons': ['calendar_incomplete'] + [None] * 30,
            }],
        })
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            write_snapshot(snapshot, directory)
            self.assertEqual(read_snapshot('2026-10', directory), snapshot)

    def test_rejects_reason_for_known_count(self):
        with self.assertRaises(ValueError):
            validate_snapshot({
                'month': '2026-10',
                'objects': [{
                    'name': 'А', 'counts': [0] * 31,
                    'reasons': ['sheet_missing'] + [None] * 30,
                }],
            })


if __name__ == '__main__':
    unittest.main()
