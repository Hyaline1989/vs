# bitrix_api.py - полная версия с поддержкой email и раздельных полей имени/фамилии/отчества
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
        """Создаёт лид для направления сотрудника с поддержкой email и раздельных полей имени/фамилии/отчества"""
        method = 'crm.lead.add'
        
        title = lead_data.get('title', 'Новое направление')
        
        # Получаем объект от агента
        agent_object = lead_data.get('agent_object', '')
        agent_email = lead_data.get('agent_email', '')
        
        # Получаем раздельные поля имени
        first_name = lead_data.get('first_name', '')
        last_name = lead_data.get('last_name', '')
        patronymic = lead_data.get('patronymic', '')
        
        # Собираем полное ФИО для комментария
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
        
        # ФИО агента
        agent_name = lead_data.get('agent_name', '')
        if not agent_name:
            agent_name = lead_data.get('directed_by', '')
        
        # Формируем поля для лида
        fields = {
            'TITLE': title,
            'NAME': first_name,           # Имя
            'LAST_NAME': last_name,       # Фамилия
            'SECOND_NAME': patronymic,    # Отчество
            'PHONE': [{'VALUE': lead_data.get('candidate_phone', ''), 'VALUE_TYPE': 'WORK'}],
            'COMMENTS': comments,
            'SOURCE_ID': lead_data.get('source_id', 'WEB'),
            'STATUS_ID': 'NEW',
            'CURRENCY_ID': 'RUB',
            'OPPORTUNITY': 0,
            AGENT_NAME_FIELD: agent_name,
            AGENT_OBJECT_FIELD: agent_object,
        }
        
        # Добавляем email в отдельное пользовательское поле (если оно есть)
        if agent_email:
            fields[AGENT_EMAIL_FIELD] = agent_email
            logger.info(f"📧 Email агента ({AGENT_EMAIL_FIELD}): {agent_email}")
        
        params = {'fields': fields}
        
        try:
            logger.info(f"Создание лида: {title}")
            logger.info(f"ФИО кандидата: {last_name} {first_name} {patronymic}")
            logger.info(f"ФИО агента ({AGENT_NAME_FIELD}): {agent_name}")
            logger.info(f"Email агента ({AGENT_EMAIL_FIELD}): {agent_email}")
            logger.info(f"Объект ({AGENT_OBJECT_FIELD}): {agent_object}")
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
            # Формируем массив файлов для поля
            file_data_array = []
            
            for file in files:
                if not file or not file.filename:
                    continue
                
                # Возвращаем указатель в начало файла
                file.seek(0)
                
                # Читаем файл и кодируем в base64
                file_content = file.read()
                file_base64 = base64.b64encode(file_content).decode('utf-8')
                
                file_data_array.append({
                    'fileData': [file.filename, file_base64]
                })
            
            if not file_data_array:
                return False
            
            # Отправляем массив файлов в поле
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
        """Создаёт лид и прикрепляет все файлы к пользовательскому полю"""
        lead_id = self.create_lead_from_direction(lead_data)
        
        if not lead_id:
            return None
        
        # Фильтруем валидные файлы
        valid_files = [f for f in files if f and f.filename] if files else []
        
        if valid_files:
            success = self.upload_files_to_lead_field(lead_id, valid_files, PASSPORT_FIELD)
            if success:
                logger.info(f"✅ {len(valid_files)} файлов прикреплены к лиду {lead_id}")
            else:
                logger.warning(f"Не удалось прикрепить файлы к лиду {lead_id}")
        
        return lead_id
    
    def get_source_id_for_direction(self):
        """Возвращает ID источника для направлений из CRM"""
        return SOURCE_AGENT
    
    # ========== МЕТОДЫ ДЛЯ СТАТУСОВ ВАХТОВИКОВ ==========
    
    def get_deals_by_agent_fullname(self, agent_fullname, date_from=None, date_to=None):
        """
        Получает сделки (лиды) для конкретного агента по полю UF_CRM_65D332164BDB2
        с фильтрацией по дате создания сделки (DATE_CREATE)
        """
        filter_params = {
            AGENT_NAME_FIELD: agent_fullname  # UF_CRM_1708339537928 - ФИО агента
        }
        
        if date_from:
            filter_params['>DATE_CREATE'] = date_from + ' 00:00:00'
        if date_to:
            filter_params['<DATE_CREATE'] = date_to + ' 23:59:59'
        
        all_leads = self._get_all_leads_raw_for_worker(filter_params)
        return self._process_leads_with_statuses(all_leads)
    
    def _get_all_leads_raw_for_worker(self, filter_params):
        """Получает все лиды с фильтрацией для статусов вахтовиков"""
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
                    AGENT_NAME_FIELD,      # UF_CRM_1708339537928 - ФИО агента
                    AGENT_OBJECT_FIELD,    # UF_CRM_1777895760218 - Объект
                    'UF_CRM_1684488791039',  # Дата заселения
                    'UF_CRM_1685531338652',  # Дата отработал 1 смену
                    'UF_CRM_1684488917199',  # Дата адаптирован 5 смен
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
    
    def _process_leads_with_statuses(self, leads):
        """Обрабатывает лиды и извлекает информацию о статусах"""
        if not leads:
            return []
        
        result = []
        for lead in leads:
            # Собираем ФИО вахтовика из полей NAME, LAST_NAME, SECOND_NAME
            first_name = lead.get('NAME', '')
            last_name = lead.get('LAST_NAME', '')
            second_name = lead.get('SECOND_NAME', '')
            
            worker_full_name = ' '.join([p for p in [last_name, first_name, second_name] if p]).strip()
            if not worker_full_name:
                worker_full_name = lead.get('TITLE', 'Не указано')
            
            result.append({
                'lead_id': lead.get('ID'),
                'title': lead.get('TITLE'),
                'worker_full_name': worker_full_name,
                'agent_full_name': lead.get(AGENT_NAME_FIELD, ''),
                'object_name': lead.get(AGENT_OBJECT_FIELD, ''),
                'deal_date': lead.get('DATE_CREATE', '')[:10] if lead.get('DATE_CREATE') else '',
                'check_in_date': lead.get('UF_CRM_1684488791039', ''),
                'shift_1_date': lead.get('UF_CRM_1685531338652', ''),
                'shift_5_date': lead.get('UF_CRM_1684488917199', '')
            })
        
        return result
    
    def sync_worker_statuses_for_agent(self, agent_fullname, date_from=None, date_to=None):
        """
        Синхронизирует статусы вахтовиков для конкретного агента
        Возвращает список обновлённых/добавленных записей
        """
        from database.worker_status import save_or_update_worker_status, update_worker_status_from_bitrix
        
        leads = self.get_deals_by_agent_fullname(agent_fullname, date_from, date_to)
        synced_count = 0
        
        for lead in leads:
            # Сохраняем основную информацию
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