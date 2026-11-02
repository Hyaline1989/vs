import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from datetime import date

import payroll_calculation


class PayrollCalculationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'test.db')
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('CREATE TABLE objects_settings(id INTEGER, name TEXT)')
            conn.execute("INSERT INTO objects_settings VALUES(1, 'Форум Авто')")
            conn.execute('CREATE TABLE candidate_rates(object_id INTEGER, day TEXT, amount INTEGER, source TEXT)')
            conn.execute('CREATE TABLE daily_snapshots(date TEXT, object_name TEXT, is_high INTEGER)')
            conn.execute("INSERT INTO daily_snapshots VALUES('2026-10-03', 'Форум Авто', 1)")
            conn.executemany('INSERT INTO candidate_rates VALUES(?,?,?,?)', [
                (1, '2026-10-01', 4000, 'priority'), (1, '2026-10-02', 5000, 'manual')])

    def tearDown(self):
        self.temp.cleanup()

    def test_groups_candidates_and_uses_direction_date_rate(self):
        deals = [
            dict(deal_id=1, candidate='Иванов', staff='Анна', object_name='Форум Авто', directed_date='2026-10-01', shift_date='2026-11-03'),
            dict(deal_id=2, candidate='Петров', staff='Анна', object_name='Форум Авто', directed_date='2026-10-02', shift_date='2026-10-05'),
        ]
        result = payroll_calculation.calculate(self.path, deals, today=date(2026,11,4))
        self.assertEqual(result['summary'], [{'staff':'Анна','candidates':2,'amount':9000,'unrated':0}])
        self.assertEqual(result['totals'], {'candidates':2,'amount':9000,'unrated':0})

    def test_default_and_priority_rates_do_not_require_saved_rows(self):
        result = payroll_calculation.calculate(self.path, [
            dict(deal_id=3, candidate='Сидоров', staff='Борис', object_name='Форум Авто', directed_date='2026-10-03', shift_date='2026-10-04'),
            dict(deal_id=4, candidate='Орлов', staff='Борис', object_name='Форум Авто', directed_date='2026-10-04', shift_date='2026-10-05')])
        self.assertEqual(result['totals']['amount'], 6500)
        self.assertEqual(result['totals']['unrated'], 0)
        self.assertEqual([row['rate_source'] for row in result['rows']], ['priority-default', 'default'])

    def test_invalid_future_and_reversed_dates_excluded(self):
        deals = [dict(deal_id=i, candidate='A', staff='B', object_name='Форум Авто',
                      directed_date=directed, shift_date=shifted)
                 for i, (directed, shifted) in enumerate([
                     ('2026-10-02','2026-10-01'), ('2026-10-01','2026-10-30'),
                     ('2026-10-01','2026-02-30'), ('2026-10-01',''),
                     ('2026-10-01','2026-10-29')])]
        result = payroll_calculation.calculate(self.path,deals,today=date(2026,10,29))
        self.assertEqual(len(result['excluded']),4)
        self.assertEqual(result['totals']['candidates'],1)

    def test_priority_aliases_combined(self):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("INSERT INTO daily_snapshots VALUES('2026-10-03','Форум Авто!',0)")
        result = payroll_calculation.calculate(self.path,[dict(deal_id=1, candidate='A', staff='B',
            object_name='Форум Авто', directed_date='2026-10-03', shift_date='2026-10-04')], today=date(2026,10,29))
        self.assertEqual(result['totals']['amount'],4000)


if __name__ == '__main__':
    unittest.main()
