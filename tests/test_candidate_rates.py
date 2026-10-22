import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
import candidate_rates as rates


class CandidateRatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / 'test.db')
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('CREATE TABLE objects_settings(id INTEGER, name TEXT)')
            conn.execute("INSERT INTO objects_settings VALUES(1, 'Форум Авто')")
            conn.execute('CREATE TABLE daily_snapshots(date TEXT, object_name TEXT, is_high INTEGER)')
            conn.executemany('INSERT INTO daily_snapshots VALUES(?,?,?)', [
                ('2026-10-01','Форум Авто',1), ('2026-10-01','Форум Авто',1),
                ('2026-10-02','Форум Авто',0)])
            rates.create_schema(conn)

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, mode='confirm', **extra):
        p = dict(object_id=1, **{'from':'2026-10-01','to':'2026-10-03'}, mode=mode)
        p['revision'] = rates.read_preview(self.path,1,p['from'],p['to'])['revision']
        return dict(p, **extra)

    def test_suggestions_and_missing_are_not_saved_by_read(self):
        cells = rates.read_calendar(self.path,'2026-10')['rows'][0]['cells']
        self.assertEqual([c['suggestion'] for c in cells[:3]], [4000,2500,None])
        self.assertTrue(all(c['amount'] is None for c in cells))
        self.assertEqual(rates.read_history(self.path,1,'2026-10-01','2026-10-31'), [])

    def test_confirm_manual_history_and_no_overwrite(self):
        result = rates.save_rates(self.path,self.payload(),7,'Катя')
        self.assertEqual(result['changed'],2)
        rates.save_rates(self.path,self.payload('manual',amount=5000,comment='Акция'),8,'Менеджер')
        result = rates.save_rates(self.path,self.payload(),7,'Катя')
        self.assertEqual(result['changed'],0)
        history = rates.read_history(self.path,1,'2026-10-01','2026-10-03')
        self.assertEqual(len(history),5)
        self.assertEqual(history[0]['actor_name'],'Менеджер')
        self.assertEqual(history[-1]['new_amount'],4000)

    def test_concurrent_changes_are_rejected(self):
        old = self.payload('manual',amount=5000,comment='Акция')
        rates.save_rates(self.path,self.payload(),7,'Катя')
        with self.assertRaises(rates.RatesConflict):
            rates.save_rates(self.path,old,8,'Другой')

    def test_changed_snapshot_does_not_change_saved_amount(self):
        rates.save_rates(self.path,self.payload(),7,'Катя')
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('UPDATE daily_snapshots SET is_high=0')
        cell = rates.read_calendar(self.path,'2026-10')['rows'][0]['cells'][0]
        self.assertEqual(cell['amount'],4000)
        self.assertEqual(cell['suggestion'],2500)

    def test_invalid_values_are_rejected_without_history(self):
        for amount in (-1, True, 2.5, '4000', 1000001):
            with self.assertRaises(ValueError):
                rates.save_rates(self.path,self.payload('manual',amount=amount,comment='Акция'),7,'Катя')
        with self.assertRaises(ValueError):
            rates.period('2026-10-05','2026-10-01')
        self.assertEqual(rates.read_history(self.path,1,'2026-10-01','2026-10-31'), [])

    def test_automatic_sync_preserves_manual_and_is_idempotent(self):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            self.assertEqual(rates.sync_priority_rates(conn), 2)
            self.assertEqual(rates.sync_priority_rates(conn), 0)
        p = self.payload('manual', amount=6000, comment='Акция')
        p['to'] = p['from']
        p['revision'] = rates.read_preview(self.path,1,p['from'],p['to'])['revision']
        rates.save_rates(self.path,p,7,'Катя')
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute('UPDATE daily_snapshots SET is_high=1')
            self.assertEqual(rates.sync_priority_rates(conn), 1)
            self.assertEqual(rates.sync_priority_rates(conn), 0)
        cells = rates.read_calendar(self.path,'2026-10')['rows'][0]['cells']
        self.assertEqual([c['amount'] for c in cells[:3]], [6000,4000,None])
        self.assertEqual(cells[0]['source'], 'manual')


if __name__ == '__main__':
    unittest.main()
