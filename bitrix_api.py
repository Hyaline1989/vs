# bitrix_api.py
# -*- coding: utf-8 -*-
import requests
from datetime import datetime
from config import *
import logging
import re

logger = logging.getLogger(__name__)

class BitrixAPI:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    def get_directed_deals_by_date(self, target_date):
        """
        Получить все сделки направленные на объекты за конкретную дату
        Исключает Перевахтовку и Приведи друга
        """
        if isinstance(target_date, str):
            date_str = target_date
        else:
            date_str = target_date.strftime('%Y-%m-%d')
        
        all_deals = self._get_all_deals_raw({
            FIELD_DATE_DIRECTED: date_str
        })
        
        filtered_deals = []
        for deal in all_deals:
            source_id = deal.get('SOURCE_ID')
            if source_id not in EXCLUDED_SOURCES:
                filtered_deals.append(deal)
        
        return self._process_deals_data(filtered_deals)
    
    def get_deals_by_office(self, target_date, office_source=None):
        """Получить сделки по конкретному офису за дату"""
        if isinstance(target_date, str):
            date_str = target_date
        else:
            date_str = target_date.strftime('%Y-%m-%d')
        
        filter_params = {FIELD_DATE_DIRECTED: date_str}
        if office_source:
            filter_params['SOURCE_ID'] = office_source
        
        all_deals = self._get_all_deals_raw(filter_params)
        
        if office_source:
            return self._process_deals_data(all_deals)
        
        filtered_deals = []
        for deal in all_deals:
            source_id = deal.get('SOURCE_ID')
            if source_id not in EXCLUDED_SOURCES:
                filtered_deals.append(deal)
        
        return self._process_deals_data(filtered_deals)
    
    def get_all_offices_stats(self, target_date):
        """Получить статистику по всем офисам за дату"""
        if isinstance(target_date, str):
            date_str = target_date
        else:
            date_str = target_date.strftime('%Y-%m-%d')
        
        result = {}
        
        # Агент
        agent_deals = self.get_deals_by_office(target_date, SOURCE_AGENT)
        result['agent'] = {
            'count': sum(agent_deals.values()) if agent_deals else 0,
            'objects': agent_deals if agent_deals else {}
        }
        
        # Поток
        potok_deals = self.get_deals_by_office(target_date, SOURCE_POTOK)
        result['potok'] = {
            'count': sum(potok_deals.values()) if potok_deals else 0,
            'objects': potok_deals if potok_deals else {}
        }
        
        # Горький52
        gorkiy_deals = self.get_deals_by_office(target_date, SOURCE_GORKIY52)
        result['gorkiy52'] = {
            'count': sum(gorkiy_deals.values()) if gorkiy_deals else 0,
            'objects': gorkiy_deals if gorkiy_deals else {}
        }
        
        # Бишкек
        bishkek_deals = self.get_deals_by_office(target_date, SOURCE_BISHKEK)
        result['bishkek'] = {
            'count': sum(bishkek_deals.values()) if bishkek_deals else 0,
            'objects': bishkek_deals if bishkek_deals else {}
        }
        
        # Комплект (все остальные, кроме исключенных)
        all_raw = self._get_all_deals_raw({FIELD_DATE_DIRECTED: date_str})
        complect_deals_raw = []
        known_sources = [SOURCE_AGENT, SOURCE_POTOK, SOURCE_GORKIY52, SOURCE_BISHKEK]
        
        for deal in all_raw:
            source_id = deal.get('SOURCE_ID')
            if source_id not in known_sources and source_id not in EXCLUDED_SOURCES:
                complect_deals_raw.append(deal)
        
        complect_deals = self._process_deals_data(complect_deals_raw)
        result['complect'] = {
            'count': sum(complect_deals.values()) if complect_deals else 0,
            'objects': complect_deals if complect_deals else {}
        }
        
        return result
    
    def _get_all_deals_raw(self, filter_params):
        """Получить сырые данные сделок для фильтрации"""
        all_deals = []
        start = 0
        limit = 50
        
        while True:
            method = 'crm.deal.list'
            params = {
                'filter': filter_params,
                'select': ['ID', 'TITLE', FIELD_DATE_DIRECTED, FIELD_COMPANY, 'SOURCE_ID'],
                'start': start
            }
            
            try:
                response = requests.post(f"{self.webhook_url}{method}", json=params, timeout=30)
                result = response.json()
                
                if 'result' in result and result['result']:
                    deals_batch = result['result']
                    all_deals.extend(deals_batch)
                    
                    if len(deals_batch) < limit:
                        break
                    
                    start += limit
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Ошибка при запросе к Bitrix24: {e}")
                break
        
        logger.info(f"Получено {len(all_deals)} сделок из Bitrix24")
        return all_deals
    
    def _process_deals_data(self, deals):
        """Обработать данные сделок и сгруппировать по компаниям (без эмодзи)"""
        if not deals:
            return {}
        
        company_ids = []
        for deal in deals:
            company_id = deal.get(FIELD_COMPANY)
            if company_id and company_id not in company_ids:
                company_ids.append(company_id)
        
        companies_info = self._get_companies_info(company_ids)
        
        grouped_data = {}
        for deal in deals:
            company_id = deal.get(FIELD_COMPANY)
            if company_id:
                company_name = companies_info.get(company_id, 'Неизвестная компания')
                company_name = self._remove_emoji(company_name)
                if company_name not in grouped_data:
                    grouped_data[company_name] = 0
                grouped_data[company_name] += 1
        
        return grouped_data
    
    def _remove_emoji(self, text):
        """Удаляет эмодзи из текста"""
        if not text:
            return text
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F1E0-\U0001F1FF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            u"\U0001F900-\U0001F9FF"
            u"\U0001FA70-\U0001FAFF"
            u"\U00002600-\U000027BF"
            u"\U0001F004-\U0001F0CF"
            u"\U0001F18E-\U0001F1FF"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub('', text).strip()
    
    def _get_companies_info(self, company_ids):
        """Получить информацию о компаниях по их ID"""
        if not company_ids:
            return {}
        
        companies_info = {}
        
        for company_id in company_ids:
            method = 'crm.company.get'
            params = {'id': company_id}
            
            try:
                response = requests.post(f"{self.webhook_url}{method}", json=params, timeout=10)
                result = response.json()
                
                if 'result' in result:
                    company_name = result['result'].get('TITLE', 'Неизвестная компания')
                    companies_info[company_id] = self._remove_emoji(company_name)
                else:
                    companies_info[company_id] = 'Неизвестная компания'
            except Exception as e:
                logger.error(f"Ошибка при получении компании {company_id}: {e}")
                companies_info[company_id] = 'Ошибка загрузки'
        
        return companies_info