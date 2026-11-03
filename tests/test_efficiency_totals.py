import csv
import io
import unittest
from PIL import Image
from manager_efficiency import rating_totals, save_rating_csv, build_rating_png


class TotalsTests(unittest.TestCase):
    def rows(self):
        rows = []
        for success, failed, avg, pause, seconds in [(1,0,60,0,120),(1,8,120,60,240)]:
            rows.append(dict(system='Комплект',manager='Менеджер',in_accepted=1,
                out_success=success,out_failed=failed,total_calls=2+failed,line_seconds=seconds,
                avg_seconds=avg,break_seconds=pause,line_time='0:02:00',avg_time='0:01:00',
                break_time='0:00:00',out_success_rate_text='100%',short_share_text='0%',
                index=50,index_text='50.0'))
        return rows

    def test_sums_and_manager_means_and_weighted_rate(self):
        result=rating_totals(self.rows())
        self.assertEqual([result[k] for k in ('in_accepted','out_success','out_failed','total_calls')],[2,2,8,12])
        self.assertEqual(result['line_time'],'0:06:00')
        self.assertEqual(result['avg_time'],'0:01:30')
        self.assertEqual(result['break_time'],'0:00:30')
        self.assertEqual(result['out_success_rate_text'],'20%')
        self.assertEqual(result['short_share_text'],'')
        self.assertEqual(result['index_text'],'')

    def test_csv_and_png(self):
        rows=self.rows()
        output=list(csv.reader(io.StringIO(save_rating_csv(rows)),delimiter=';'))
        self.assertEqual(output[-1][1],'Итого')
        self.assertEqual(output[-1][-3:],['20%','',''])
        with Image.open(build_rating_png(rows,'02.11.2026')) as image:
            self.assertEqual(image.height,44+28*(len(rows)+2)+88)
        self.assertEqual(len(rows),2)

    def test_empty_and_no_outgoing(self):
        self.assertEqual(rating_totals([])['out_success_rate_text'],'0%')
        row=self.rows()[0]
        row.update(out_success=0,out_failed=0)
        self.assertEqual(rating_totals([row])['out_success_rate'],0)


if __name__=='__main__': unittest.main()
