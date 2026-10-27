import sqlite3
import unittest
from datetime import date, datetime, timezone
from demand_history import SCHEMA, record_current, report_from_connection
from scripts.import_demand_history import transfer


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.addCleanup(self.c.close)
        self.c.execute(SCHEMA)
        self.c.executescript('''
            CREATE TABLE vacancy_objects(id INTEGER,name TEXT);
            CREATE TABLE vacancy_positions(id INTEGER,object_id INTEGER);
            CREATE TABLE vacancy_requirements(position_id INTEGER,date TEXT,
                rf_men INTEGER,rf_women INTEGER,rf_family INTEGER,cis_men INTEGER,cis_women INTEGER,cis_family INTEGER);
            CREATE TABLE current_requirements(object_name TEXT,rf_men INTEGER,rf_women INTEGER,rf_family INTEGER,cis_men INTEGER,cis_women INTEGER,cis_family INTEGER);
            CREATE TABLE daily_snapshots(date TEXT,object_name TEXT,is_high INTEGER);
            INSERT INTO vacancy_objects VALUES(1,'A');
            INSERT INTO vacancy_positions VALUES(1,1);
            INSERT INTO vacancy_requirements VALUES(1,'2026-10-01',10,0,0,0,0,0);
            INSERT INTO vacancy_requirements VALUES(1,'2026-10-02',0,0,0,0,0,0);
        ''')
        self.start, self.end = date(2026,10,1), date(2026,10,3)

    def test_repeat_zero_missing_and_marker(self):
        self.assertEqual(transfer(self.c,self.start,self.end),2)
        self.assertEqual(transfer(self.c,self.start,self.end),0)
        result = report_from_connection(self.c,self.start,self.end)['objects'][0]
        self.assertEqual(result['counts'],[10,0,None])
        self.assertEqual(result['legacy'],[True,True,False])

    def test_existing_protected_and_current_clears_marker(self):
        self.c.execute("INSERT INTO demand_history VALUES('2026-10-01','A',6,'2026-10-01')")
        self.assertEqual(transfer(self.c,self.start,self.end),1)
        self.c.execute("INSERT INTO current_requirements VALUES('A',3,0,0,0,0,0)")
        record_current(self.c,now=datetime(2026,10,2,tzinfo=timezone.utc))
        result = report_from_connection(self.c,self.start,self.end)['objects'][0]
        self.assertEqual(result['counts'],[6,3,None])
        self.assertEqual(result['legacy'],[False,False,False])

    def test_rollback(self):
        self.c.commit()
        self.c.execute('BEGIN')
        transfer(self.c,self.start,self.end)
        self.c.rollback()
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM demand_history').fetchone()[0],0)


if __name__ == '__main__':
    unittest.main()
