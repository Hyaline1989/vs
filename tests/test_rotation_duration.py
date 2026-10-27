import unittest
import tempfile
from pathlib import Path
from datetime import date, timedelta
from openpyxl import load_workbook
import rotation_duration as rd
import report_refresh_store as queue


class RotationTests(unittest.TestCase):
    def test_break_boundary(self):
        start=date(2026,8,1)
        for gap, expected in [(7,1),(8,2)]:
            days={start:{'W'},start+timedelta(days=1):{'УБ'},start+timedelta(days=1+gap):{'W'}}
            self.assertEqual(len(rd.episodes(days,start,date(2026,8,31))),expected)

    def test_maximum_and_cap(self):
        start=date(2026,7,1)
        days={start+timedelta(days=i):{'W'} for i in range(60)}
        run=rd.episodes(days,start,date(2026,10,25))[0]
        self.assertEqual(run['shifts'],55)
        self.assertEqual(run['actual'],60)
        self.assertTrue(run['success'])
        self.assertTrue(run['inferred'])

    def test_trim_median(self):
        runs=[dict(shifts=i,early=False,success=False,inferred=False) for i in range(1,21)]
        stats=rd.statistics_for(runs,[])
        self.assertEqual(stats['trim'],2)
        self.assertEqual(stats['remaining'],16)
        self.assertEqual(stats['median'],10.5)
        self.assertEqual(stats['trimmed'],10.5)

    def part(self,name,people):
        return rd.validate_part(dict(month='2026-08',batch_id='a'*32,key_id='b'*64,
            expected_objects=['A','B'],object=dict(name=name,reason=None,available=[True]*31,people=people)))

    def person(self,id,shifts,excluded=False):
        return dict(id=id*64,excluded=excluded,marks=[['W'] if i<shifts else [] for i in range(31)])

    def test_publish_company_exclusions_excel(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(rd.save_part(self.part('A',[self.person('1',10),self.person('2',3),self.person('3',0)]),tmp))
            self.assertFalse((Path(tmp)/'2026-08.json').exists())
            self.assertTrue(rd.save_part(self.part('B',[self.person('1',20),self.person('2',1,True)]),tmp))
            args=(date(2026,8,1),date(2026,8,31),'2026-08')
            objects=rd.build_report(*args,'objects',tmp)
            self.assertEqual(objects['rows'][0]['count'],2)
            company=rd.build_report(*args,'company',tmp)
            self.assertEqual(company['rows'][0]['count'],1)
            self.assertEqual(company['rows'][0]['mean'],20)
            self.assertEqual(company['rows'][0]['cohort_count'],1)
            workbook=load_workbook(rd.export_workbook(company))
            self.assertEqual(len(workbook.sheetnames),6)
            self.assertEqual(workbook['Средняя']['D5'].value,20)

    def test_cursor_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            task=queue.request_refresh('rotations','2026-08',tmp)
            claimed=queue.claim_pending(tmp)
            self.assertEqual(claimed['cursor'],0)
            self.assertTrue(queue.advance_rotation_refresh('2026-08',task['id'],0,tmp))
            self.assertFalse(queue.advance_rotation_refresh('2026-08',task['id'],0,tmp))
            self.assertEqual(queue.claim_pending(tmp)['cursor'],1)

    def test_cohort_new_rotation_not_added(self):
        start=date(2026,8,1)
        days={start:{'З'},date(2026,8,2):{'W'},date(2026,8,3):{'ОВ'},date(2026,9,1):{'W'}}
        runs=rd.episodes(days,start,date(2026,9,30))
        cohort=[r for r in runs if r['arrival'].month==8]
        self.assertEqual(len(cohort),1)
        self.assertEqual(cohort[0]['shifts'],1)
        self.assertTrue(cohort[0]['early'])
        self.assertTrue(cohort[0]['success'])


if __name__=='__main__':
    unittest.main()
