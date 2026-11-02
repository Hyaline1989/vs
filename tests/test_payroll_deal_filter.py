"""Изолированная проверка методов Битрикса без импорта настроек и без сети."""
import ast
from datetime import datetime
from pathlib import Path
import re
import unittest

tree = ast.parse((Path(__file__).resolve().parents[1] / 'bitrix_api.py').read_text(encoding='utf-8-sig'))
klass = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ShiftReportAPI')
klass.body = [n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name in ('get_payroll_deals','_extract_date','_get_filtered_deals')]
ns = dict(datetime=datetime,re=re)
for name in ('FIELD_COMPANY','FIELD_DATE_DIRECTED','FIELD_WORKED_1_SHIFT','FIELD_CC_OPERATOR_REPORT',
             'FIELD_CC_OPERATOR','FIELD_AGENT_FIO','SOURCE_AGENT','SOURCE_BISHKEK','SOURCE_POTOK'):
    ns[name]=name
from unittest.mock import Mock
ns.update(logger=Mock(),is_operator=lambda value: str(value).casefold().startswith('опер'))
exec(compile(ast.Module(body=[klass],type_ignores=[]),'bitrix_api.py','exec'),ns)


class PayrollFilterTests(unittest.TestCase):
    def test_only_complect_and_no_agent_without_name(self):
        api=ns['ShiftReportAPI']()
        deals=[]
        for i,(src,staff,agent) in enumerate([
            ('normal','Комплект Анна',''),('SOURCE_POTOK','Анна',''),
            ('SOURCE_BISHKEK','Анна',''),('SOURCE_AGENT','Анна',''),
            ('normal','Сервис Анна',''),('normal','Поток Анна',''),
            ('normal','Опер Анна',''),('normal','Спутник Анна',''),
            ('normal','Анна','Агент')]):
            deals.append(dict(ID=str(i),SOURCE_ID=src,FIELD_CC_OPERATOR_REPORT=staff,
                FIELD_AGENT_FIO=agent,FIELD_COMPANY='1',FIELD_DATE_DIRECTED='2026-10-01',
                FIELD_WORKED_1_SHIFT='2026-10-02'))
        api._get_deals_by_date=lambda *args: deals
        api._get_companies_info=lambda ids: {'1':'Объект'}
        self.assertEqual([r['deal_id'] for r in api.get_payroll_deals('2026-10-01','2026-10-31')],['0'])

    def test_bad_date_does_not_crash(self):
        self.assertEqual(ns['ShiftReportAPI']._extract_date('31.02.2026'),'')


if __name__=='__main__': unittest.main()
