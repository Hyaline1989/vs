# bitrix_api.py - полная версия с получением данных из сделки и отчётами по 1 смене
# -*- coding: utf-8 -*-
import requests
import re
import base64
from datetime import datetime
from config import *
import logging
from normalizer import ObjectNameNormalizer

logger = logging.getLogger(__name__)

# Константа для поля "Скан паспорта"
PASSPORT_FIELD = "UF_CRM_1707988048727"
# Константа для поля "ФИО агента"
AGENT_NAME_FIELD = "UF_CRM_1708339537928"
# Константа для поля "Объект от агента"
AGENT_OBJECT_FIELD = "UF_CRM_1777895760218"
# Константа для поля "Email агента"
AGENT_EMAIL_FIELD = "UF_CRM_1778049472057"

# Константы для полей статусов вахтовиков (в СДЕЛКЕ)
CHECK_IN_FIELD = "UF_CRM_1684488791039"      # Дата заселения
SHIFT_1_FIELD = "UF_CRM_1685531338652"      # Дата отработал 1 смену
SHIFT_5_FIELD = "UF_CRM_1684488917199"      # Дата адаптирован (5 смен)


class BitrixAPI:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self.normalizer = ObjectNameNormalizer()
    
    def get_directed_deals_by_date(self, target_date):
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
        if isinstance(target_date, str):
            date_str = target_date
        else:
            date_str = target_date.strftime('%Y-%m-%d')
        
        result = {}
        
        agent_deals = self.get_deals_by_office(target_date, SOURCE_AGENT)
        result['agent'] = {
            'count': sum(agent_deals.values()) if agent_deals else 0,
            'objects': agent_deals if agent_deals else {}
        }
        
        potok_deals = self.get_deals_by_office(target_date, SOURCE_POTOK)
        result['potok'] = {
            'count': sum(potok_deals.values()) if potok_deals else 0,
            'objects': potok_deals if potok_deals else {}
        }
        
        gorkiy_deals = self.get_deals_by_office(target_date, SOURCE_GORKIY52)
        result['gorkiy52'] = {
            'count': sum(gorkiy_deals.values()) if gorkiy_deals else 0,
            'objects': gorkiy_deals if gorkiy_deals else {}
        }
        
        bishkek_deals = self.get_deals_by_office(target_date, SOURCE_BISHKEK)
        result['bishkek'] = {
            'count': sum(bishkek_deals.values()) if bishkek_deals else 0,
            'objects': bishkek_deals if bishkek_deals else {}
        }
        
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
                company_name = self._remove_emoji_only(company_name)
                if company_name not in grouped_data:
                    grouped_data[company_name] = 0
                grouped_data[company_name] += 1
        
        return grouped_data
    
    def _remove_emoji_only(self, text):
        """Удаляет только эмодзи, сохраняя оригинальный регистр"""
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
        result = emoji_pattern.sub('', text).strip()
        result = ' '.join(result.split())
        return result
    
    def _get_companies_info(self, company_ids):
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
                    companies_info[company_id] = company_name
                else:
                    companies_info[company_id] = 'Неизвестная компания'
            except Exception as e:
                logger.error(f"Ошибка при получении компании {company_id}: {e}")
                companies_info[company_id] = 'Ошибка загрузки'
        
        return companies_info
    
    # ========== МЕТОДЫ ДЛЯ НАПРАВЛЕНИЯ СОТРУДНИКА (ЛИДЫ) ==========
    
    def create_lead_from_direction(self, lead_data):
        """Создаёт лид для направления сотрудника"""
        method = 'crm.lead.add'
        
        title = lead_data.get('title', 'Новое направление')
        agent_object = lead_data.get('agent_object', '')
        agent_email = lead_data.get('agent_email', '')
        
        first_name = lead_data.get('first_name', '')
        last_name = lead_data.get('last_name', '')
        patronymic = lead_data.get('patronymic', '')
        
        full_name = ' '.join([p for p in [last_name, first_name, patronymic] if p])
        
        comments = f"""📋 ИНФОРМАЦИЯ О НАПРАВЛЕНИИ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 Кандидат: {full_name if full_name else 'Не указан'}
📞 Телефон: {lead_data.get('candidate_phone', 'Не указан')}
🏢 Объект: {agent_object}
💼 Должность: {lead_data.get('position_name', 'Не указана')}
👨‍💼 Направил: {lead_data.get('directed_by', 'Неизвестно')}

📧 Email агента: {agent_email if agent_email else 'Не указан'}

📝 КОММЕНТАРИЙ:
{lead_data.get('comment', 'Нет комментария')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        agent_name = lead_data.get('agent_name', '')
        if not agent_name:
            agent_name = lead_data.get('directed_by', '')
        
        fields = {
            'TITLE': title,
            'NAME': first_name,
            'LAST_NAME': last_name,
            'SECOND_NAME': patronymic,
            'PHONE': [{'VALUE': lead_data.get('candidate_phone', ''), 'VALUE_TYPE': 'WORK'}],
            'COMMENTS': comments,
            'SOURCE_ID': lead_data.get('source_id', 'WEB'),
            'STATUS_ID': 'NEW',
            'CURRENCY_ID': 'RUB',
            'OPPORTUNITY': 0,
            AGENT_NAME_FIELD: agent_name,
            AGENT_OBJECT_FIELD: agent_object,
        }
        
        if agent_email:
            fields[AGENT_EMAIL_FIELD] = agent_email
        
        params = {'fields': fields}
        
        try:
            logger.info(f"Создание лида: {title}")
            response = requests.post(f"{self.webhook_url}{method}", json=params, timeout=30)
            result = response.json()
            
            if 'result' in result:
                lead_id = result['result']
                logger.info(f"✅ Создан лид ID: {lead_id}")
                return lead_id
            else:
                logger.error(f"Ошибка создания лида: {result}")
                return None
        except Exception as e:
            logger.error(f"Ошибка при создании лида: {e}")
            return None
    
    def upload_files_to_lead_field(self, lead_id, files, field_name):
        """Загружает несколько файлов в пользовательское поле лида через base64"""
        if not files:
            return True
        
        try:
            file_data_array = []
            
            for file in files:
                if not file or not file.filename:
                    continue
                
                file.seek(0)
                file_content = file.read()
                file_base64 = base64.b64encode(file_content).decode('utf-8')
                
                file_data_array.append({
                    'fileData': [file.filename, file_base64]
                })
            
            if not file_data_array:
                return False
            
            method = 'crm.lead.update'
            params = {
                'id': lead_id,
                'fields': {
                    field_name: file_data_array
                }
            }
            
            logger.info(f"Загрузка {len(file_data_array)} файлов в поле {field_name} лида {lead_id}")
            
            response = requests.post(f"{self.webhook_url}{method}", json=params, timeout=120)
            result = response.json()
            
            if 'result' in result:
                logger.info(f"✅ {len(file_data_array)} файлов прикреплены к полю {field_name} лида {lead_id}")
                return True
            else:
                logger.error(f"Ошибка прикрепления файлов: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка загрузки файлов в поле лида: {e}")
            return False
    
    def create_lead_with_files(self, lead_data, files=None):
        """Создаёт лид и прикрепляет все файлы"""
        lead_id = self.create_lead_from_direction(lead_data)
        
        if not lead_id:
            return None
        
        valid_files = [f for f in files if f and f.filename] if files else []
        
        if valid_files:
            success = self.upload_files_to_lead_field(lead_id, valid_files, PASSPORT_FIELD)
            if success:
                logger.info(f"✅ {len(valid_files)} файлов прикреплены к лиду {lead_id}")
            else:
                logger.warning(f"Не удалось прикрепить файлы к лиду {lead_id}")
        
        return lead_id
    
    def get_source_id_for_direction(self):
        return SOURCE_AGENT
    
    # ========== МЕТОДЫ ДЛЯ СТАТУСОВ ВАХТОВИКОВ (из СДЕЛКИ) ==========
    
    def _get_deal_by_lead_id(self, lead_id):
        """Находит сделку, связанную с лидом"""
        method = 'crm.deal.list'
        params = {
            'filter': {'LEAD_ID': lead_id},
            'select': ['ID', 'LEAD_ID', 'TITLE']
        }
        
        try:
            response = requests.post(f"{self.webhook_url}{method}", json=params, timeout=30)
            result = response.json()
            
            if 'result' in result and result['result']:
                deals = result['result']
                if deals:
                    return deals[0]['ID']
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска сделки по лиду {lead_id}: {e}")
            return None
    
    def _get_deal_statuses(self, deal_id):
        """Получает статусные поля из сделки"""
        method = 'crm.deal.get'
        params = {'id': deal_id}
        
        try:
            response = requests.post(f"{self.webhook_url}{method}", json=params, timeout=30)
            result = response.json()
            
            if 'result' in result:
                deal = result['result']
                
                check_in = deal.get(CHECK_IN_FIELD, '')
                shift_1 = deal.get(SHIFT_1_FIELD, '')
                shift_5 = deal.get(SHIFT_5_FIELD, '')
                
                # Очищаем даты
                for val in [check_in, shift_1, shift_5]:
                    if val and len(str(val)) > 10:
                        if val == check_in:
                            check_in = str(check_in)[:10]
                        elif val == shift_1:
                            shift_1 = str(shift_1)[:10]
                        elif val == shift_5:
                            shift_5 = str(shift_5)[:10]
                
                return {
                    'check_in_date': check_in,
                    'shift_1_date': shift_1,
                    'shift_5_date': shift_5
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения статусов из сделки {deal_id}: {e}")
            return None
    
    def get_deals_by_agent_fullname(self, agent_fullname, date_from=None, date_to=None):
        """Получает лиды агента и обогащает их данными из связанных сделок"""
        filter_params = {
            AGENT_NAME_FIELD: agent_fullname
        }
        
        if date_from:
            filter_params['>DATE_CREATE'] = date_from + ' 00:00:00'
        if date_to:
            filter_params['<DATE_CREATE'] = date_to + ' 23:59:59'
        
        all_leads = self._get_all_leads_raw_for_worker(filter_params)
        return self._process_leads_with_deal_statuses(all_leads)
    
    def _get_all_leads_raw_for_worker(self, filter_params):
        """Получает все лиды с фильтрацией"""
        all_leads = []
        start = 0
        limit = 50
        
        while True:
            method = 'crm.lead.list'
            params = {
                'filter': filter_params,
                'select': [
                    'ID', 'TITLE', 'NAME', 'LAST_NAME', 'SECOND_NAME',
                    'DATE_CREATE',
                    AGENT_NAME_FIELD,
                    AGENT_OBJECT_FIELD,
                ],
                'start': start
            }
            
            try:
                response = requests.post(f"{self.webhook_url}{method}", json=params, timeout=30)
                result = response.json()
                
                if 'result' in result and result['result']:
                    leads_batch = result['result']
                    all_leads.extend(leads_batch)
                    
                    if len(leads_batch) < limit:
                        break
                    
                    start += limit
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Ошибка при запросе лидов к Bitrix24: {e}")
                break
        
        logger.info(f"Получено {len(all_leads)} лидов из Bitrix24 для агента")
        return all_leads
    
    def _process_leads_with_deal_statuses(self, leads):
        """Обрабатывает лиды и получает статусы из связанных сделок"""
        if not leads:
            return []
        
        result = []
        for lead in leads:
            # Собираем ФИО вахтовика
            first_name = lead.get('NAME', '')
            last_name = lead.get('LAST_NAME', '')
            second_name = lead.get('SECOND_NAME', '')
            
            worker_full_name = ' '.join([p for p in [last_name, first_name, second_name] if p]).strip()
            if not worker_full_name:
                worker_full_name = lead.get('TITLE', 'Не указано')
            
            # Ищем связанную сделку
            deal_id = self._get_deal_by_lead_id(lead.get('ID'))
            
            check_in = ''
            shift_1 = ''
            shift_5 = ''
            
            if deal_id:
                logger.info(f"🔍 Найдена сделка {deal_id} для лида {lead.get('ID')}")
                statuses = self._get_deal_statuses(deal_id)
                if statuses:
                    check_in = statuses.get('check_in_date', '')
                    shift_1 = statuses.get('shift_1_date', '')
                    shift_5 = statuses.get('shift_5_date', '')
                    logger.info(f"📋 Из сделки {deal_id}: заселение='{check_in}', 1 смена='{shift_1}', 5 смен='{shift_5}'")
            else:
                logger.warning(f"⚠️ Для лида {lead.get('ID')} не найдена связанная сделка")
            
            # Преобразуем формат DD.MM.YYYY в YYYY-MM-DD если нужно
            for date_val in [check_in, shift_1, shift_5]:
                if date_val and '.' in date_val:
                    try:
                        parts = date_val.split('.')
                        if len(parts) == 3:
                            new_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                            if date_val == check_in:
                                check_in = new_date
                            elif date_val == shift_1:
                                shift_1 = new_date
                            elif date_val == shift_5:
                                shift_5 = new_date
                    except:
                        pass
            
            logger.info(f"📋 Лид {lead.get('ID')}: заселение='{check_in}', 1 смена='{shift_1}', 5 смен='{shift_5}'")
            
            deal_date = lead.get('DATE_CREATE', '')
            if deal_date and len(str(deal_date)) > 10:
                deal_date = str(deal_date)[:10]
            
            result.append({
                'lead_id': lead.get('ID'),
                'title': lead.get('TITLE'),
                'worker_full_name': worker_full_name,
                'agent_full_name': lead.get(AGENT_NAME_FIELD, ''),
                'object_name': lead.get(AGENT_OBJECT_FIELD, ''),
                'deal_date': deal_date,
                'check_in_date': check_in,
                'shift_1_date': shift_1,
                'shift_5_date': shift_5
            })
        
        return result
    
    def sync_worker_statuses_for_agent(self, agent_fullname, date_from=None, date_to=None):
        from database.worker_status import save_or_update_worker_status
        
        leads = self.get_deals_by_agent_fullname(agent_fullname, date_from, date_to)
        synced_count = 0
        
        for lead in leads:
            save_or_update_worker_status(
                lead_id=lead['lead_id'],
                worker_full_name=lead['worker_full_name'],
                agent_full_name=lead['agent_full_name'],
                deal_date=lead['deal_date'],
                check_in_date=lead['check_in_date'],
                shift_1_date=lead['shift_1_date'],
                shift_5_date=lead['shift_5_date']
            )
            synced_count += 1
        
        logger.info(f"Синхронизировано {synced_count} записей для агента {agent_fullname}")
        return synced_count
    
    def get_lead_by_id(self, lead_id):
        """Получает данные лида и статусы из связанной сделки"""
        method = 'crm.lead.get'
        params = {'id': lead_id}
        
        try:
            response = requests.post(f"{self.webhook_url}{method}", json=params, timeout=30)
            result = response.json()
            
            if 'result' in result:
                lead = result['result']
                
                first_name = lead.get('NAME', '')
                last_name = lead.get('LAST_NAME', '')
                second_name = lead.get('SECOND_NAME', '')
                worker_full_name = ' '.join([p for p in [last_name, first_name, second_name] if p]).strip()
                if not worker_full_name:
                    worker_full_name = lead.get('TITLE', 'Не указано')
                
                # Ищем связанную сделку
                deal_id = self._get_deal_by_lead_id(lead_id)
                check_in = ''
                shift_1 = ''
                shift_5 = ''
                
                if deal_id:
                    statuses = self._get_deal_statuses(deal_id)
                    if statuses:
                        check_in = statuses.get('check_in_date', '')
                        shift_1 = statuses.get('shift_1_date', '')
                        shift_5 = statuses.get('shift_5_date', '')
                
                return {
                    'lead_id': lead.get('ID'),
                    'worker_full_name': worker_full_name,
                    'agent_full_name': lead.get(AGENT_NAME_FIELD, ''),
                    'object_name': lead.get(AGENT_OBJECT_FIELD, ''),
                    'check_in_date': check_in,
                    'shift_1_date': shift_1,
                    'shift_5_date': shift_5
                }
            else:
                logger.error(f"Ошибка получения лида {lead_id}: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка при получении лида {lead_id}: {e}")
            return None
    
    def debug_lead_fields(self, lead_id):
        """Диагностика лида и связанной сделки"""
        method = 'crm.lead.get'
        params = {'id': lead_id}
        
        try:
            response = requests.post(f"{self.webhook_url}{method}", json=params, timeout=30)
            result = response.json()
            
            if 'result' in result:
                lead = result['result']
                logger.info(f"\n{'='*60}")
                logger.info(f"Диагностика лида {lead_id}")
                logger.info(f"{'='*60}")
                
                # Ищем связанную сделку
                deal_id = self._get_deal_by_lead_id(lead_id)
                logger.info(f"Связанная сделка: {deal_id}")
                
                if deal_id:
                    # Получаем статусы из сделки
                    statuses = self._get_deal_statuses(deal_id)
                    if statuses:
                        logger.info(f"Дата заселения (из сделки): {statuses.get('check_in_date')}")
                        logger.info(f"Дата 1 смены (из сделки): {statuses.get('shift_1_date')}")
                        logger.info(f"Дата 5 смен (из сделки): {statuses.get('shift_5_date')}")
                
                logger.info(f"{'='*60}\n")
                return lead
            else:
                logger.error(f"Ошибка получения лида: {result}")
                return None
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return None


# ========== КЛАСС ДЛЯ ОТЧЁТОВ ПО 1 СМЕНЕ (ИЗ ТЕЛЕГРАМ БОТА) ==========

class ShiftReportAPI:
    """API для отчётов по отработавшим 1 смену"""
    
    def __init__(self, webhook_url=BITRIX_WEBHOOK_URL):
        self.webhook_url = webhook_url
    
    def _get_filtered_deals(self, start_date_str, end_date_str):
        """Возвращает сделки, прошедшие все фильтры, но без группировки."""
        deals = self._get_deals_by_date(start_date_str, end_date_str)
        
        # Оставляем только с отработанной сменой (заполненное и не 'N')
        worked = [d for d in deals if d.get(FIELD_WORKED_1_SHIFT) and d.get(FIELD_WORKED_1_SHIFT) != 'N']
        
        # Без заполненного ФИО агента
        no_agent = [d for d in worked if not d.get(FIELD_AGENT_FIO)]
        
        # Исключаем операторов (всех, чьё имя начинается с "Опер")
        clean = [
            d for d in no_agent
            if not is_operator(d.get(FIELD_CC_OPERATOR, ''))
            and not is_operator(d.get(FIELD_CC_OPERATOR_REPORT, ''))
        ]
        return clean
    
    def _get_deals_by_date(self, start_date_str, end_date_str):
        """Загружает сделки за период только с фильтром по дате направления."""
        all_deals = []
        start = 0
        limit = 50
        filter_params = {
            f'>={FIELD_DATE_DIRECTED}': start_date_str,
            f'<={FIELD_DATE_DIRECTED}': end_date_str
        }
        while True:
            params = {
                'filter': filter_params,
                'select': [
                    'ID', 'TITLE',
                    FIELD_DATE_DIRECTED,
                    FIELD_COMPANY,
                    'SOURCE_ID',
                    FIELD_CC_OPERATOR,
                    FIELD_CC_OPERATOR_REPORT,
                    FIELD_WORKED_1_SHIFT,
                    FIELD_AGENT_FIO
                ],
                'start': start
            }
            try:
                resp = requests.post(f"{self.webhook_url}crm.deal.list", json=params, timeout=30)
                result = resp.json()
                if 'result' in result and result['result']:
                    batch = result['result']
                    all_deals.extend(batch)
                    if len(batch) < limit:
                        break
                    start += limit
                else:
                    break
            except Exception as e:
                logger.error(f"Ошибка запроса к Bitrix24: {e}")
                break
        logger.info(f"Получено {len(all_deals)} сделок для отчёта по 1 смене")
        return all_deals
    
    def get_shift_report(self, start_date_str, end_date_str):
        """Отчёт по отработавшим 1 смену с разбивкой по компаниям."""
        deals = self._get_filtered_deals(start_date_str, end_date_str)
        return self._group_by_companies(deals)
    
    def _group_by_companies(self, deals):
        """Группировка по компаниям (для отчёта по объектам)."""
        categories = {'Поток': [], 'Бишкек': [], 'Комплект': []}
        exclude = {SOURCE_AGENT}
        
        for d in deals:
            src = d.get('SOURCE_ID')
            if src in exclude:
                continue
            if src == SOURCE_POTOK:
                categories['Поток'].append(d)
            elif src == SOURCE_BISHKEK:
                categories['Бишкек'].append(d)
            else:
                categories['Комплект'].append(d)
        
        report = {}
        for cat_name, deal_list in categories.items():
            if not deal_list:
                report[cat_name] = {}
                continue
            company_ids = list({d.get(FIELD_COMPANY) for d in deal_list if d.get(FIELD_COMPANY)})
            companies_info = self._get_companies_info(company_ids)
            
            grouped = {}
            for d in deal_list:
                cid = d.get(FIELD_COMPANY)
                if cid and cid in companies_info:
                    cname = companies_info[cid]
                    grouped[cname] = grouped.get(cname, 0) + 1
            report[cat_name] = grouped
        return report
    
    def get_staff_report(self, start_date_str, end_date_str):
        """Отчёт по отработавшим 1 смену с разбивкой по сотрудникам."""
        deals = self._get_filtered_deals(start_date_str, end_date_str)
        return self._group_by_staff(deals)
    
    def _group_by_staff(self, deals):
        """Группировка по полю Сотрудник Колл-центра (ОТЧЕТ)."""
        categories = {'Поток': [], 'Бишкек': [], 'Комплект': []}
        exclude = {SOURCE_AGENT}
        
        for d in deals:
            src = d.get('SOURCE_ID')
            if src in exclude:
                continue
            if src == SOURCE_POTOK:
                categories['Поток'].append(d)
            elif src == SOURCE_BISHKEK:
                categories['Бишкек'].append(d)
            else:
                categories['Комплект'].append(d)
        
        report = {}
        for cat_name, deal_list in categories.items():
            if not deal_list:
                report[cat_name] = {}
                continue
            grouped = {}
            for d in deal_list:
                staff = d.get(FIELD_CC_OPERATOR_REPORT)
                if staff and not is_operator(staff):
                    grouped[staff] = grouped.get(staff, 0) + 1
            report[cat_name] = grouped
        return report
    
    def _get_companies_info(self, company_ids):
        """Получает названия компаний по ID"""
        if not company_ids:
            return {}
        info = {}
        for cid in company_ids:
            try:
                resp = requests.post(f"{self.webhook_url}crm.company.get", json={'id': cid}, timeout=10)
                data = resp.json()
                if 'result' in data:
                    info[cid] = data['result'].get('TITLE', 'Неизвестная компания')
            except Exception as e:
                logger.error(f"Ошибка компании {cid}: {e}")
                info[cid] = 'Ошибка загрузки'
        return info
    
    def add_emoji(self, company_name):
        """Добавляет эмодзи к названию компании"""
        for key, emoji in COMPANY_EMOJIS.items():
            if key in company_name:
                return f"{emoji} {company_name}"
        return f"{DEFAULT_EMOJI} {company_name}"