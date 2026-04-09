# routes/dashboard.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, redirect
from flask_login import current_user
from datetime import datetime, timedelta
import re
import logging

from database import get_user_module_permissions
from bitrix_api import BitrixAPI
from comparer import DataComparer
from config import BITRIX_WEBHOOK_URL

logger = logging.getLogger(__name__)

# Создаём blueprint для дашборда
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api')

# Инициализируем API (будет переопределено в app.py)
bitrix_api = None
comparer = None

# Кэш для данных
_data_cache = {}
_cache_timestamps = {}
CACHE_DURATION = 60

def get_cached_data(cache_key, fetch_func, *args, **kwargs):
    """Получает данные из кэша или загружает их"""
    now = datetime.now()
    if cache_key in _data_cache and cache_key in _cache_timestamps:
        if (now - _cache_timestamps[cache_key]).seconds < CACHE_DURATION:
            return _data_cache[cache_key]
    
    data = fetch_func(*args, **kwargs)
    _data_cache[cache_key] = data
    _cache_timestamps[cache_key] = now
    return data

def clear_cache():
    """Очищает кэш данных"""
    global _data_cache, _cache_timestamps
    _data_cache = {}
    _cache_timestamps = {}
    logger.info("Кэш данных очищен")

def init_dashboard_apis(bitrix, google, comp):
    """Инициализирует API для dashboard blueprint"""
    global bitrix_api, comparer
    bitrix_api = bitrix
    comparer = comp


@dashboard_bp.route('/dashboard')
def dashboard():
    """Получение данных дашборда за дату"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    module_perms = get_user_module_permissions(current_user.id)
    if not module_perms.get('dashboard', False):
        return jsonify({'error': 'Forbidden', 'message': 'У вас нет доступа к дашборду'}), 403
    
    try:
        date_str = request.args.get('date')
        if not date_str:
            return jsonify({'error': 'Не указана дата'}), 400
        
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return jsonify({'error': 'Неверный формат даты'}), 400
        
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Используем кэш для данных Bitrix
        cache_key = f"dashboard_{date_str}"
        offices_stats = get_cached_data(cache_key, bitrix_api.get_all_offices_stats, target_date)
        
        # Сравнение всегда загружаем свежее из БД
        comparison = comparer.compare_by_date(target_date)
        
        response = {
            'date': target_date.strftime('%d.%m.%Y'),
            'offices': offices_stats,
            'comparison': {
                'only_plan': comparison.get('only_plan', {}),
                'only_fact': comparison.get('only_fact', {}),
                'negative_delta': comparison.get('negative_delta', {}),
                'positive_delta': comparison.get('positive_delta', {}),
                'zero_delta': comparison.get('zero_delta', {})
            },
            'summary': comparison.get('summary', {
                'total_plan': 0, 'total_fact': 0, 'percent': 0, 'delta': 0
            })
        }
        return jsonify(response)
    except Exception as e:
        logger.error(f"Ошибка в dashboard: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/dashboard/today')
def dashboard_today():
    """Получение данных дашборда за сегодня"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    module_perms = get_user_module_permissions(current_user.id)
    if not module_perms.get('dashboard', False):
        return jsonify({'error': 'Forbidden'}), 403
    
    today = datetime.now().strftime('%Y-%m-%d')
    return redirect(f'/api/dashboard?date={today}')


@dashboard_bp.route('/update-requirements', methods=['POST'])
def update_requirements():
    """Ручное обновление потребностей (очистка кэша)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    module_perms = get_user_module_permissions(current_user.id)
    if not module_perms.get('dashboard', False):
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        clear_cache()
        return jsonify({'status': 'ok', 'message': 'Кэш очищен, данные будут загружены заново'})
    except Exception as e:
        logger.error(f"Ошибка при обновлении: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/report')
def report():
    """Формирование отчёта за период"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    module_perms = get_user_module_permissions(current_user.id)
    if not module_perms.get('dashboard', False):
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        from_date = request.args.get('from')
        to_date = request.args.get('to')
        
        if not from_date or not to_date:
            return jsonify({'error': 'Не указан период'}), 400
        
        start = datetime.strptime(from_date, '%Y-%m-%d')
        end = datetime.strptime(to_date, '%Y-%m-%d')
        
        result = []
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            
            try:
                cache_key = f"report_{date_str}"
                offices = get_cached_data(cache_key, bitrix_api.get_all_offices_stats, current)
                comparison = comparer.compare_by_date(current)
            except Exception as e:
                logger.error(f"Ошибка при получении данных за {date_str}: {e}")
                current += timedelta(days=1)
                continue
            
            day_data = {
                'date': current.strftime('%d.%m.%Y'),
                'objects': {}
            }
            
            all_objects = set()
            for office in offices.values():
                all_objects.update(office.get('objects', {}).keys())
            
            for obj in all_objects:
                day_data['objects'][obj] = {
                    'plan': 0,
                    'complect': offices.get('complect', {}).get('objects', {}).get(obj, 0),
                    'potok': offices.get('potok', {}).get('objects', {}).get(obj, 0),
                    'gorkiy': offices.get('gorkiy52', {}).get('objects', {}).get(obj, 0),
                    'agent': offices.get('agent', {}).get('objects', {}).get(obj, 0),
                    'bishkek': offices.get('bishkek', {}).get('objects', {}).get(obj, 0)
                }
                
                if comparison.get('only_plan', {}).get(obj):
                    day_data['objects'][obj]['plan'] = comparison['only_plan'][obj].get('count', 0)
                for section in ['negative_delta', 'zero_delta', 'positive_delta']:
                    if comparison.get(section, {}).get(obj):
                        day_data['objects'][obj]['plan'] = comparison[section][obj].get('plan', 0)
            
            result.append(day_data)
            current += timedelta(days=1)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Ошибка при формировании отчёта: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500