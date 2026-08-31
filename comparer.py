# comparer.py
# -*- coding: utf-8 -*-
from normalizer import ObjectNameNormalizer
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DataComparer:
    def __init__(self, bitrix_api, google_api=None):
        self.bitrix = bitrix_api
        self.google = google_api  # Оставляем для совместимости, но не используем
        self.normalizer = ObjectNameNormalizer()
    
    def _get_plan_requirements(self, target_date):
        """
        Получает план (потребности) из БД
        """
        from database import get_plan_requirements_for_date
        return get_plan_requirements_for_date(target_date)
    
    def compare_by_date(self, target_date, deals=None):
        """Сравнивает данные за указанную дату"""
        try:
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d')
            
            logger.info("=" * 50)
            logger.info(f"Сравниваем данные за {target_date.strftime('%Y-%m-%d')}")
            
            # ========== ИЗМЕНЕНО: Получаем план из БД вместо Google Sheets ==========
            requirements_data = self._get_plan_requirements(target_date)
            
            # Преобразуем в формат для сравнения
            requirements = {}
            priorities = {}
            for obj_name, data in requirements_data.items():
                if isinstance(data, dict):
                    requirements[obj_name] = data['count']
                    if data.get('is_high', False):
                        priorities[obj_name] = True
                        logger.info(f"🔴 ПРИОРИТЕТНЫЙ ОБЪЕКТ В СРАВНЕНИИ: {obj_name}")
                else:
                    requirements[obj_name] = data
            
            logger.info(f"Из БД (план) получено {len(requirements)} объектов")
            logger.info(f"Приоритетных объектов: {len(priorities)}")
            
            # Получаем фактические направленные из Bitrix
            # Если факты уже загружены вызывающим кодом, используем их повторно.
            # Это позволяет дашборду не выполнять ещё один запрос к Bitrix.
            if deals is None:
                deals = self.bitrix.get_directed_deals_by_date(target_date)
            logger.info(f"Из Bitrix получено {len(deals)} объектов")
            
            # Нормализуем названия для сравнения
            req_normalized = self.normalizer.normalize_dict(requirements)
            deals_normalized = self.normalizer.normalize_dict(deals)
            priorities_normalized = {
                self.normalizer.normalize(name)
                for name in priorities
            }
            
            logger.info(f"Нормализованные План (БД): {list(req_normalized.keys())[:10]}")
            logger.info(f"Нормализованные Bitrix: {list(deals_normalized.keys())[:10]}")
            
            # Создаем обратную карту для восстановления оригинальных названий
            original_names = {}
            
            for name in requirements:
                norm_name = self.normalizer.normalize(name)
                original_names[norm_name] = name
            
            for name in deals:
                norm_name = self.normalizer.normalize(name)
                original_names[norm_name] = name
            
            # Результаты
            only_plan = {}
            only_fact = {}
            matched = {}
            
            deals_remaining = dict(deals_normalized)
            
            for norm_name, plan in req_normalized.items():
                if norm_name in deals_remaining:
                    fact = deals_remaining[norm_name]
                    original = original_names.get(norm_name, norm_name)
                    
                    matched[original] = {
                        'plan': plan,
                        'fact': fact,
                        'delta': fact - plan,
                        'is_high': norm_name in priorities_normalized
                    }
                    logger.info(f"Совпадение: '{original}' план={plan} факт={fact}")
                    del deals_remaining[norm_name]
                else:
                    original = original_names.get(norm_name, norm_name)
                    only_plan[original] = {
                        'count': plan,
                        'is_high': norm_name in priorities_normalized
                    }
                    logger.info(f"Только в плане: '{original}' план={plan}")
            
            for norm_name, fact in deals_remaining.items():
                original = original_names.get(norm_name, norm_name)
                only_fact[original] = fact
                logger.info(f"Только в факте: '{original}' факт={fact}")
            
            # Разделяем matched по дельте
            negative_delta = {}
            positive_delta = {}
            zero_delta = {}
            
            for obj_name, data in matched.items():
                if data['delta'] < 0:
                    negative_delta[obj_name] = data
                elif data['delta'] > 0:
                    positive_delta[obj_name] = data
                else:
                    zero_delta[obj_name] = data
            
            negative_delta = dict(sorted(negative_delta.items(), 
                                        key=lambda x: x[1]['delta']))
            positive_delta = dict(sorted(positive_delta.items(), 
                                        key=lambda x: x[1]['delta'], reverse=True))
            
            total_plan = sum(requirements.values()) if requirements else 0
            total_fact = sum(deals.values()) if deals else 0
            percent = round((total_fact / total_plan * 100), 1) if total_plan > 0 else 0
            
            result = {
                'only_plan': only_plan,
                'only_fact': only_fact,
                'negative_delta': negative_delta,
                'positive_delta': positive_delta,
                'zero_delta': zero_delta,
                'summary': {
                    'total_plan': total_plan,
                    'total_fact': total_fact,
                    'percent': percent,
                    'delta': total_fact - total_plan
                }
            }
            
            logger.info(f"ИТОГИ за {target_date.strftime('%Y-%m-%d')}:")
            logger.info(f"  План всего: {total_plan}, Факт всего: {total_fact}")
            logger.info(f"  only_plan ({len(only_plan)}): {list(only_plan.keys())[:5]}")
            logger.info(f"  only_fact ({len(only_fact)}): {list(only_fact.keys())[:5]}")
            logger.info(f"  negative_delta ({len(negative_delta)})")
            logger.info(f"  positive_delta ({len(positive_delta)})")
            logger.info("=" * 50)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка в compare_by_date: {e}", exc_info=True)
            return {
                'only_plan': {},
                'only_fact': {},
                'negative_delta': {},
                'positive_delta': {},
                'zero_delta': {},
                'summary': {
                    'total_plan': 0,
                    'total_fact': 0,
                    'percent': 0,
                    'delta': 0
                }
            }
    
    def compare_today(self):
        """Сравнивает данные за сегодня (для обратной совместимости)"""
        return self.compare_by_date(datetime.now())
