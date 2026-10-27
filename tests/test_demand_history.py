import sqlite3
import unittest
from datetime import date, datetime, timezone
from demand_history import SCHEMA, record_current, report_from_connection


class DemandHistoryTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.execute(SCHEMA)
        self.conn.execute('CREATE TABLE current_requirements(object_name TEXT, rf_men INTEGER,rf_women INTEGER,rf_family INTEGER,cis_men INTEGER,cis_women INTEGER,cis_family INTEGER)')
        self.conn.execute('CREATE TABLE daily_snapshots(date TEXT,object_name TEXT,is_high INTEGER)')
        self.now=datetime(2026,10,27,12,tzinfo=timezone.utc)

    def test_latest_not_max_and_zero(self):
        self.conn.execute("INSERT INTO current_requirements VALUES('A',10,0,0,0,0,0)")
        for count in (10,6,0):
            self.conn.execute('UPDATE current_requirements SET rf_men=?',(count,))
            record_current(self.conn,now=self.now)
            self.assertEqual(self.conn.execute('SELECT count FROM demand_history').fetchone()[0],count)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM demand_history').fetchone()[0],1)

    def test_history_survives_deletion_missing_and_priority(self):
        self.conn.execute("INSERT INTO current_requirements VALUES('A',2,3,1,0,0,0)")
        record_current(self.conn,now=self.now)
        self.conn.execute('DELETE FROM current_requirements')
        self.conn.executemany('INSERT INTO daily_snapshots VALUES(?,?,?)', [('2026-10-27','A',1),('2026-10-27','A',1)])
        data=report_from_connection(self.conn,date(2026,10,26),date(2026,10,27))
        self.assertEqual(data['objects'][0]['counts'],[None,6])
        self.assertEqual(data['objects'][0]['priorities'],[None,True])
        self.assertEqual(data['totals'],[None,6])

    def test_transaction_rollback(self):
        self.conn.commit()
        self.conn.execute("INSERT INTO current_requirements VALUES('A',1,0,0,0,0,0)")
        record_current(self.conn,now=self.now)
        self.conn.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM demand_history').fetchone()[0],0)

    def test_empty_positions_explicit_zero(self):
        record_current(self.conn,now=self.now,extra_names=['A'])
        self.assertEqual(self.conn.execute('SELECT count FROM demand_history').fetchone()[0],0)

    def test_period_limit(self):
        with self.assertRaises(ValueError):
            report_from_connection(self.conn,date(2020,1,1),date(2026,1,1))


if __name__=='__main__':unittest.main()
