# google_sheets.py - исправленная версия (без циклического импорта)
# -*- coding: utf-8 -*-

import csv
import requests
from io import StringIO
import logging
import re
from config import GOOGLE_SHEET_CSV_URL, GOOGLE_SHEETS_UPDATE_INTERVAL_SECONDS
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GoogleSheetsAPI:
    def __init__(self):
        self.csv_url = GOOGLE_SHEET_CSV_URL
        self._csv_cache = None
        self._csv_cache_time = None
        self._cache_duration = GOOGLE_SHEETS_UPDATE_INTERVAL_SECONDS
    
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
    
    def _normalize_object_name(self, name):
        """Нормализует название объекта (удаляет эмодзи и лишнее)"""
        if not name:
            return ""
        
        # Удаляем эмодзи
        name = self._remove_emoji(name)
        
        # Удаляем лишние пробелы
        name = ' '.join(str(name).split())
        
        # Удаляем ООО, ЗАО и другие организационно-правовые формы
        name = re.sub(r'(?i)\b(ооо|зао|оао|ао|ип|гк|пк|кфх|тнв|нп|рн|llc|inc|gmbh)\b[.\s]*', '', name)
        
        # Удаляем кавычки и лишние символы
        name = re.sub(r'["\'«»]', '', name)
        
        # Удаляем лишние пробелы в начале и конце
        name = name.strip()
        
        return name
    
    def _is_high_priority(self, value):
        """
        Проверяет, является ли значение признаком высокого приоритета
        Поддерживает: 'high', '1', '+', 'да', 'yes', 'true', 'vip', 'х', 'priority', '!', 'высокий', 'важный'
        """
        if not value:
            return False
        value = str(value).strip().lower()
        high_values = ['high', '1', '+', 'да', 'yes', 'true', 'vip', 'х', 'priority', '!', 'высокий', 'важный']
        return value in high_values
    
    def _get_csv_data(self, force_refresh=False):
        """Получает CSV данные из Google таблицы с кэшированием"""
        now = datetime.now()
        
        if not force_refresh and self._csv_cache and self._csv_cache_time:
            cache_age = (now - self._csv_cache_time).seconds
            if cache_age < self._cache_duration:
                logger.debug(f"Используем кэш CSV (возраст: {cache_age} сек)")
                return self._csv_cache
        
        try:
            logger.info(f"Загружаем данные из Google таблицы (force_refresh={force_refresh})")
            response = requests.get(self.csv_url, timeout=30)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                self._csv_cache = response.text
                self._csv_cache_time = now
                logger.info(f"Данные успешно загружены, размер: {len(response.text)} символов")
                return self._csv_cache
            else:
                logger.error(f"Ошибка загрузки: {response.status_code}")
                return self._csv_cache if self._csv_cache else None
                
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных: {e}")
            return self._csv_cache if self._csv_cache else None
    
    def get_vacancy_data(self):
        """
        Получает данные о вакансиях из Google Sheets
        (Используется ТОЛЬКО для миграции, после миграции можно отключить)
        """
        try:
            csv_text = self._get_csv_data(force_refresh=False)
            if not csv_text:
                logger.error("CSV данные не получены для вакансий")
                return {}
            
            first_line = csv_text.split('\n')[0]
            delimiter = ',' if ',' in first_line and first_line.count(',') >= first_line.count(';') else ';'
            
            csv_data = StringIO(csv_text)
            reader = csv.reader(csv_data, delimiter=delimiter)
            rows = list(reader)
            
            if not rows:
                logger.error("Нет строк в CSV")
                return {}
            
            result = {}
            
            # Получаем заголовки для определения столбцов
            headers = rows[0] if rows else []
            logger.info(f"Заголовки CSV для вакансий: {headers[:15] if len(headers) > 15 else headers}")
            
            # Определяем индексы столбцов (по умолчанию)
            object_col_idx = 0      # Столбец A - объект
            position_col_idx = 1    # Столбец B - должность
            men_rf_col_idx = 2      # Столбец C - мужчины РФ
            women_rf_col_idx = 3    # Столбец D - женщины РФ
            family_rf_col_idx = 4   # Столбец E - семейные РФ
            men_cis_col_idx = 5     # Столбец F - мужчины СНГ
            women_cis_col_idx = 6   # Столбец G - женщины СНГ
            family_cis_col_idx = 7  # Столбец H - семейные СНГ
            
            # Пытаемся найти столбцы по заголовкам
            for i, header in enumerate(headers):
                header_lower = str(header).lower().strip()
                if 'должность' in header_lower or 'позиция' in header_lower or 'position' in header_lower:
                    position_col_idx = i
                elif ('мужчин' in header_lower or 'муж' in header_lower) and ('рф' in header_lower or 'росси' in header_lower):
                    men_rf_col_idx = i
                elif ('женщин' in header_lower or 'жен' in header_lower) and ('рф' in header_lower or 'росси' in header_lower):
                    women_rf_col_idx = i
                elif ('семей' in header_lower or 'семья' in header_lower) and ('рф' in header_lower or 'росси' in header_lower):
                    family_rf_col_idx = i
                elif ('мужчин' in header_lower or 'муж' in header_lower) and ('снг' in header_lower):
                    men_cis_col_idx = i
                elif ('женщин' in header_lower or 'жен' in header_lower) and ('снг' in header_lower):
                    women_cis_col_idx = i
                elif ('семей' in header_lower or 'семья' in header_lower) and ('снг' in header_lower):
                    family_cis_col_idx = i
            
            logger.info(f"Индексы столбцов:")
            logger.info(f"  Объект: {object_col_idx}, Должность: {position_col_idx}")
            logger.info(f"  РФ: муж={men_rf_col_idx}, жен={women_rf_col_idx}, сем={family_rf_col_idx}")
            logger.info(f"  СНГ: муж={men_cis_col_idx}, жен={women_cis_col_idx}, сем={family_cis_col_idx}")
            
            # Обрабатываем строки (пропускаем заголовок)
            for row_num, row in enumerate(rows[1:], start=2):
                if len(row) <= object_col_idx:
                    continue
                
                object_name = str(row[object_col_idx]).strip() if len(row) > object_col_idx else ''
                if not object_name or object_name == 'Объект' or object_name.lower() == 'объект':
                    continue
                
                # Пропускаем строки с итогами
                if 'итого' in object_name.lower() or 'total' in object_name.lower():
                    continue
                
                # Получаем название должности
                position_name = str(row[position_col_idx]).strip() if len(row) > position_col_idx else ''
                
                # Пропускаем строки без должности
                if not position_name:
                    continue
                
                # Пропускаем служебные значения
                if position_name.lower() in ['', '-', '–', '—', '0', 'итого', 'всего', 'итог', 'total']:
                    continue
                
                # Проверяем, что должность не равна названию объекта (убираем дублирование)
                if position_name.lower() == object_name.lower():
                    logger.debug(f"Строка {row_num}: пропущена (должность = объект): {object_name}")
                    continue
                
                # Пропускаем служебные строки
                skip_patterns = ['объект', 'итого', 'всего', 'название', 'должность', 'потребность', 'приоритет']
                should_skip = False
                for pattern in skip_patterns:
                    if pattern in position_name.lower():
                        should_skip = True
                        break
                if should_skip:
                    logger.debug(f"Строка {row_num}: пропущена (служебная должность): {position_name}")
                    continue
                
                # Нормализуем название объекта
                normalized_name = self._normalize_object_name(object_name)
                
                # Инициализируем объект в результате, если его ещё нет
                if normalized_name not in result:
                    result[normalized_name] = {
                        'rf': {'men': 0, 'women': 0, 'family': 0},
                        'cis': {'men': 0, 'women': 0, 'family': 0},
                        'positions': []
                    }
                
                # Парсим количество для РФ
                men_rf = 0
                women_rf = 0
                family_rf = 0
                
                if len(row) > men_rf_col_idx and row[men_rf_col_idx]:
                    try:
                        val = str(row[men_rf_col_idx]).replace(',', '.').strip()
                        if val and val not in ['', '-']:
                            men_rf = int(float(val))
                    except:
                        pass
                
                if len(row) > women_rf_col_idx and row[women_rf_col_idx]:
                    try:
                        val = str(row[women_rf_col_idx]).replace(',', '.').strip()
                        if val and val not in ['', '-']:
                            women_rf = int(float(val))
                    except:
                        pass
                
                if len(row) > family_rf_col_idx and row[family_rf_col_idx]:
                    try:
                        val = str(row[family_rf_col_idx]).replace(',', '.').strip()
                        if val and val not in ['', '-']:
                            family_rf = int(float(val))
                    except:
                        pass
                
                # Парсим количество для СНГ
                men_cis = 0
                women_cis = 0
                family_cis = 0
                
                if len(row) > men_cis_col_idx and row[men_cis_col_idx]:
                    try:
                        val = str(row[men_cis_col_idx]).replace(',', '.').strip()
                        if val and val not in ['', '-']:
                            men_cis = int(float(val))
                    except:
                        pass
                
                if len(row) > women_cis_col_idx and row[women_cis_col_idx]:
                    try:
                        val = str(row[women_cis_col_idx]).replace(',', '.').strip()
                        if val and val not in ['', '-']:
                            women_cis = int(float(val))
                    except:
                        pass
                
                if len(row) > family_cis_col_idx and row[family_cis_col_idx]:
                    try:
                        val = str(row[family_cis_col_idx]).replace(',', '.').strip()
                        if val and val not in ['', '-']:
                            family_cis = int(float(val))
                    except:
                        pass
                
                # Добавляем должность если есть хоть какие-то значения
                if men_rf > 0 or women_rf > 0 or family_rf > 0 or men_cis > 0 or women_cis > 0 or family_cis > 0:
                    # Проверяем, не дублируется ли уже такая должность
                    existing_position = None
                    for pos in result[normalized_name]['positions']:
                        if pos['name'].lower() == position_name.lower():
                            existing_position = pos
                            break
                    
                    if existing_position:
                        # Суммируем с существующей должностью
                        existing_position['rf']['men'] += men_rf
                        existing_position['rf']['women'] += women_rf
                        existing_position['rf']['family'] += family_rf
                        existing_position['cis']['men'] += men_cis
                        existing_position['cis']['women'] += women_cis
                        existing_position['cis']['family'] += family_cis
                        logger.debug(f"Строка {row_num}: обновлена существующая должность {position_name} для {normalized_name}")
                    else:
                        # Добавляем новую должность
                        result[normalized_name]['positions'].append({
                            'name': position_name,
                            'rf': {'men': men_rf, 'women': women_rf, 'family': family_rf},
                            'cis': {'men': men_cis, 'women': women_cis, 'family': family_cis}
                        })
                        logger.debug(f"Строка {row_num}: добавлена должность {position_name} для {normalized_name}")
                    
                    # Суммируем общие итоги по РФ
                    result[normalized_name]['rf']['men'] += men_rf
                    result[normalized_name]['rf']['women'] += women_rf
                    result[normalized_name]['rf']['family'] += family_rf
                    
                    # Суммируем общие итоги по СНГ
                    result[normalized_name]['cis']['men'] += men_cis
                    result[normalized_name]['cis']['women'] += women_cis
                    result[normalized_name]['cis']['family'] += family_cis
            
            # Логируем результат
            logger.info(f"Загружено {len(result)} объектов из CSV для вакансий")
            for obj_name, data in result.items():
                logger.info(f"  {obj_name}:")
                logger.info(f"    РФ: муж={data['rf']['men']}, жен={data['rf']['women']}, сем={data['rf']['family']}")
                logger.info(f"    СНГ: муж={data['cis']['men']}, жен={data['cis']['women']}, сем={data['cis']['family']}")
                logger.info(f"    должностей={len(data['positions'])}")
                for pos in data['positions']:
                    logger.info(f"      - {pos['name']}: РФ(м={pos['rf']['men']},ж={pos['rf']['women']},с={pos['rf']['family']}) | СНГ(м={pos['cis']['men']},ж={pos['cis']['women']},с={pos['cis']['family']})")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения данных о вакансиях: {e}", exc_info=True)
            return {}
    
    def debug_csv_structure(self):
        """Отладочный метод для анализа структуры CSV"""
        logger.info("=== АНАЛИЗ СТРУКТУРЫ CSV ===")
        csv_text = self._get_csv_data(force_refresh=True)
        if not csv_text:
            logger.error("CSV данные не получены")
            return False
        
        first_line = csv_text.split('\n')[0]
        logger.info(f"Первая строка: {first_line}")
        
        delimiter = ',' if ',' in first_line and first_line.count(',') >= first_line.count(';') else ';'
        logger.info(f"Разделитель: '{delimiter}'")
        
        csv_data = StringIO(csv_text)
        reader = csv.reader(csv_data, delimiter=delimiter)
        rows = list(reader)
        
        logger.info(f"Всего строк: {len(rows)}")
        
        if rows:
            headers = rows[0]
            logger.info(f"Заголовки ({len(headers)}):")
            for i, h in enumerate(headers):
                logger.info(f"  {i}: '{h}'")
        
        # Показываем первые 30 строк для анализа
        logger.info("Первые 30 строк данных:")
        for i, row in enumerate(rows[1:31], start=2):
            if len(row) >= 2:
                obj = row[0].strip() if row[0] else ''
                pos = row[1].strip() if len(row) > 1 else ''
                men_rf = row[2].strip() if len(row) > 2 else ''
                women_rf = row[3].strip() if len(row) > 3 else ''
                family_rf = row[4].strip() if len(row) > 4 else ''
                men_cis = row[5].strip() if len(row) > 5 else ''
                women_cis = row[6].strip() if len(row) > 6 else ''
                family_cis = row[7].strip() if len(row) > 7 else ''
                logger.info(f"  Строка {i}: Объект='{obj}', Должность='{pos}', РФ(м={men_rf},ж={women_rf},с={family_rf}), СНГ(м={men_cis},ж={women_cis},с={family_cis})")
        
        logger.info("=== КОНЕЦ АНАЛИЗА ===")
        return True
    
    def debug_csv_content(self):
        """Отладочный метод для проверки содержимого CSV"""
        logger.info("=== ОТЛАДКА CSV ===")
        csv_text = self._get_csv_data(force_refresh=True)
        if not csv_text:
            logger.error("CSV данные не получены")
            return False
        
        first_line = csv_text.split('\n')[0]
        logger.info(f"Первая строка: {first_line}")
        
        delimiter = ',' if ',' in first_line and first_line.count(',') >= first_line.count(';') else ';'
        logger.info(f"Разделитель: '{delimiter}'")
        
        csv_data = StringIO(csv_text)
        reader = csv.reader(csv_data, delimiter=delimiter)
        rows = list(reader)
        
        logger.info(f"Всего строк: {len(rows)}")
        if rows:
            logger.info(f"Заголовки ({len(rows[0])}): {rows[0]}")
        
        vacancy_data = self.get_vacancy_data()
        logger.info(f"Данные вакансий: {len(vacancy_data)} объектов")
        for name, data in list(vacancy_data.items())[:10]:
            logger.info(f"  {name}: РФ(м={data['rf']['men']},ж={data['rf']['women']},с={data['rf']['family']}) | СНГ(м={data['cis']['men']},ж={data['cis']['women']},с={data['cis']['family']})")
        
        logger.info("=== КОНЕЦ ОТЛАДКИ ===")
        return True