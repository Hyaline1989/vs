import unittest
from test_uis_call_attribution import ns
from incoming_calls import report_calls, incoming_summary, BLOCK_ROUTE
from manager_efficiency import calculate_efficiency_rating, rating_totals, save_rating_csv, build_rating_png


class IncomingTests(unittest.TestCase):
    def call(self, id=1, **kwargs):
        data=dict(id=id,direction='in',is_lost=True,finish_reason='no_success_operator_call',
            clean_talk_duration=0,employees=[dict(employee_id=i,employee_full_name=f'Менеджер {i}') for i in range(3)])
        data.update(kwargs)
        return data

    def test_five_calls_not_fifteen_assignments(self):
        calls=[self.call(i) for i in range(1,6)]
        rows=report_calls(ns['UISAPI'](),'Комплект',calls+calls)
        self.assertEqual(len(rows),5)
        rating=calculate_efficiency_rating(rows)
        self.assertEqual(rating_totals(rating)['in_missed'],5)
        self.assertEqual(rating_totals(rating)['total_calls'],5)
        self.assertTrue(rating[0]['company_unassigned'])

    def test_blocks_technical_and_early_hangup(self):
        rows=report_calls(ns['UISAPI'](),'Комплект',[
            self.call(1,finish_reason='numa_in_black_list'),
            self.call(2,finish_reason='sip_offline',scenario_operations=[{'name':n} for n in BLOCK_ROUTE]),
            self.call(3,finish_reason='no_operation'),
            self.call(4,finish_reason='subscriber_disconnects',employees=[]),
            self.call(5,finish_reason='sip_offline')])
        self.assertEqual(incoming_summary(rows),dict(accepted=0,missed=1,technical=2,blocked_old=1,blocked_new=1))
        self.assertEqual(rating_totals(calculate_efficiency_rating(rows))['total_calls'],1)

    def test_answered_is_not_missed_by_others(self):
        rows=report_calls(ns['UISAPI'](),'Комплект',[self.call(is_lost=False,
            first_talked_employee_id=1,clean_talk_duration=30)])
        rating=calculate_efficiency_rating(rows)
        self.assertEqual(len(rating),1)
        self.assertEqual(rating[0]['manager'],'Менеджер 1')
        self.assertEqual(rating[0]['in_accepted'],1)
        self.assertEqual(rating[0]['in_missed'],0)
        self.assertIn('Вх неприн',save_rating_csv(rating))
        self.assertGreater(len(build_rating_png(rating,'03.11.2026').getvalue()),100)

    def test_missed_grouped_and_strict_thirty_seconds(self):
        api=ns['UISAPI']()
        calls=[self.call(1,employees=[dict(employee_id=1,employee_full_name='Анна')]),self.call(2)]
        for i,seconds in enumerate((0,30,31),10):
            calls.append(self.call(i,direction='out',clean_talk_duration=seconds,
                employees=[dict(employee_id=1,employee_full_name='Анна',is_talked=True)]))
        rating=calculate_efficiency_rating(report_calls(api,'Комплект',calls))
        lost=next(r for r in rating if r.get('lost_row'))
        anna=next(r for r in rating if r['manager']=='Анна')
        self.assertEqual(lost['manager'],'Потерянные звонки')
        self.assertEqual(lost['in_missed'],2)
        self.assertEqual(anna['in_missed'],0)
        self.assertEqual(anna['out_over_30'],1)
        self.assertEqual(anna['out_success'],2)
        self.assertEqual(rating_totals(rating)['total_calls'],5)
        self.assertEqual(rating_totals(rating)['out_over_30'],1)


    def test_failed_over_fifteen_uses_total_duration(self):
        calls = [self.call(i, direction='out', clean_talk_duration=0,
                          total_duration=seconds,
                          employees=[dict(employee_id=1, employee_full_name='Анна')])
                 for i, seconds in enumerate((0, 15, 16, 40), 20)]
        rating = calculate_efficiency_rating(report_calls(ns['UISAPI'](), 'Комплект', calls))
        self.assertEqual(rating[0]['out_failed_over_15'], 2)
        self.assertEqual(rating[0]['out_failed'], 4)
        self.assertEqual(rating_totals(rating)['out_failed_over_15'], 2)
        self.assertEqual(rating_totals(rating)['total_calls'], 4)
        self.assertIn('Менеджер;Исх неусп >15 сек;Исх усп >30 сек;Вх неприн', save_rating_csv(rating))


if __name__=='__main__': unittest.main()
