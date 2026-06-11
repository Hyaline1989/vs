# routes/dashboard.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, redirect
from flask_login import current_user
from datetime import datetime, timedelta
import re
import logging
import sqlite3

from database import get_user_module_permissions, DB_NAME
from bitrix_api import BitrixAPI, ShiftReportAPI
from comparer import DataComparer
from config import BITRIX_WEBHOOK_URL

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api')

bitrix_api = None
comparer = None

_data_cache = {}
_cache_timestamps = {}
CACHE_DURATION = 60

def get_cached_data(cache_key, fetch_func, *args, **kwargs):
    now = datetime.now()
    if cache_key in _data_cache and cache_key in _cache_timestamps:
        if (now - _cache_timestamps[cache_key]).seconds < CACHE_DURATION:
            return _data_cache[cache_key]
    
    data = fetch_func(*args, **kwargs)
    _data_cache[cache_key] = data
    _cache_timestamps[cache_key] = now
    return data

def clear_cache():
    global _data_cache, _cache_timestamps
    _data_cache = {}
    _cache_timestamps = {}
    logger.info("Кэш данных очищен")

def init_dashboard_apis(bitrix, comp):
    global bitrix_api, comparer
    bitrix_api = bitrix
    comparer = comp


@dashboard_bp.route('/dashboard')
def dashboard():
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
        
        cache_key = f"dashboard_{date_str}"
        offices_stats = get_cached_data(cache_key, bitrix_api.get_all_offices_stats, target_date)
        
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
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    module_perms = get_user_module_permissions(current_user.id)
    if not module_perms.get('dashboard', False):
        return jsonify({'error': 'Forbidden'}), 403
    
    today = datetime.now().strftime('%Y-%m-%d')
    return redirect(f'/api/dashboard?date={today}')


@dashboard_bp.route('/update-requirements', methods=['POST'])
def update_requirements():
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
    """ОПТИМИЗИРОВАННЫЙ отчёт - сначала из снапшотов, при отсутствии - из Bitrix"""
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
        
        from database import check_snapshot_exists, get_snapshot_report
        
        start = datetime.strptime(from_date, '%Y-%m-%d')
        end = datetime.strptime(to_date, '%Y-%m-%d')
        
        # Проверяем, все ли даты есть в снапшотах
        all_dates_exist = True
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            if not check_snapshot_exists(date_str):
                all_dates_exist = False
                break
            current += timedelta(days=1)
        
        if all_dates_exist:
            # Быстрый путь - из снапшотов
            logger.info(f"Отчёт из снапшотов за {from_date} - {to_date}")
            snapshots_data = get_snapshot_report(from_date, to_date)
            
            result = []
            for date_str, objects in snapshots_data.items():
                day_data = {
                    'date': datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y'),
                    'objects': {}
                }
                for obj in objects:
                    day_data['objects'][obj['object_name']] = {
                        'plan': obj['plan'],
                        'is_high': obj['is_high'],
                        'complect': obj['complect'],
                        'potok': obj['potok'],
                        'gorkiy': obj['gorkiy'],
                        'agent': obj['agent'],
                        'bishkek': obj['bishkek']
                    }
                result.append(day_data)
            
            return jsonify(result)
        
        # Если снапшотов нет - используем старый метод
        logger.warning(f"Снапшоты отсутствуют за некоторые даты, используем прямой запрос к Bitrix")
        
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT vr.date, vo.name, 
                   SUM(vr.rf_men + vr.rf_women + vr.rf_family + 
                       vr.cis_men + vr.cis_women + vr.cis_family) as total_plan,
                   MAX(vr.is_high) as is_high
            FROM vacancy_requirements vr
            JOIN vacancy_positions vp ON vp.id = vr.position_id
            JOIN vacancy_objects vo ON vo.id = vp.object_id
            WHERE vr.date BETWEEN ? AND ?
            GROUP BY vr.date, vo.id, vo.name
            ORDER BY vr.date, vo.name
        ''', (from_date, to_date))
        
        plan_rows = cursor.fetchall()
        
        plans_by_date = {}
        for row in plan_rows:
            date = row['date']
            obj_name = row['name']
            plan = row['total_plan'] or 0
            is_high = bool(row['is_high'])
            
            if date not in plans_by_date:
                plans_by_date[date] = {}
            plans_by_date[date][obj_name] = {
                'plan': plan,
                'is_high': is_high
            }
        
        dates_list = []
        current = start
        while current <= end:
            dates_list.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        
        def get_all_offices_stats_batch(dates):
            result = {}
            for target_date in dates:
                date_obj = datetime.strptime(target_date, '%Y-%m-%d')
                try:
                    cache_key = f"report_{target_date}"
                    offices = get_cached_data(cache_key, bitrix_api.get_all_offices_stats, date_obj)
                    
                    if target_date not in result:
                        result[target_date] = {}
                    
                    for office_name, office_data in offices.items():
                        for obj_name, count in office_data.get('objects', {}).items():
                            if obj_name not in result[target_date]:
                                result[target_date][obj_name] = {
                                    'complect': 0, 'potok': 0, 'gorkiy': 0, 'agent': 0, 'bishkek': 0
                                }
                            if office_name == 'complect':
                                result[target_date][obj_name]['complect'] += count
                            elif office_name == 'potok':
                                result[target_date][obj_name]['potok'] += count
                            elif office_name == 'gorkiy52':
                                result[target_date][obj_name]['gorkiy'] += count
                            elif office_name == 'agent':
                                result[target_date][obj_name]['agent'] += count
                            elif office_name == 'bishkek':
                                result[target_date][obj_name]['bishkek'] += count
                except Exception as e:
                    logger.error(f"Ошибка получения данных за {target_date}: {e}")
                    if target_date not in result:
                        result[target_date] = {}
            return result
        
        facts_by_date = get_all_offices_stats_batch(dates_list)
        
        result = []
        for date in dates_list:
            date_plans = plans_by_date.get(date, {})
            date_facts = facts_by_date.get(date, {})
            all_objects = set(date_plans.keys()) | set(date_facts.keys())
            
            day_data = {
                'date': datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m.%Y'),
                'objects': {}
            }
            
            has_any_data = False
            for obj in all_objects:
                plan_info = date_plans.get(obj, {'plan': 0, 'is_high': False})
                fact_info = date_facts.get(obj, {})
                
                total_sent = (fact_info.get('complect', 0) + fact_info.get('potok', 0) + 
                             fact_info.get('gorkiy', 0) + fact_info.get('agent', 0) + 
                             fact_info.get('bishkek', 0))
                
                if plan_info['plan'] == 0 and total_sent == 0:
                    continue
                
                day_data['objects'][obj] = {
                    'plan': plan_info['plan'],
                    'is_high': plan_info['is_high'],
                    'complect': fact_info.get('complect', 0),
                    'potok': fact_info.get('potok', 0),
                    'gorkiy': fact_info.get('gorkiy', 0),
                    'agent': fact_info.get('agent', 0),
                    'bishkek': fact_info.get('bishkek', 0)
                }
                has_any_data = True
            
            if has_any_data:
                result.append(day_data)
        
        conn.close()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Ошибка при формировании отчёта: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ========== ЭНДПОИНТЫ ДЛЯ УПРАВЛЕНИЯ СНАПШОТАМИ ==========

@dashboard_bp.route('/snapshot/generate', methods=['POST'])
def generate_snapshot():
    """Генерирует снапшот для указанной даты (или сегодня)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        data = request.get_json() or {}
        date_str = data.get('date')
        
        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            target_date = datetime.now()
        
        date_key = target_date.strftime('%Y-%m-%d')
        
        logger.info(f"Генерация снапшота за {date_key} пользователем {current_user.username}")
        
        from database import get_plan_requirements_for_date, save_daily_snapshots_batch, delete_snapshots_for_date
        
        offices_stats = bitrix_api.get_all_offices_stats(target_date)
        plans = get_plan_requirements_for_date(target_date)
        
        delete_snapshots_for_date(date_key)
        
        snapshots = []
        
        for office_name, office_data in offices_stats.items():
            for obj_name, count in office_data.get('objects', {}).items():
                plan_info = plans.get(obj_name, {})
                snapshots.append({
                    'object_name': obj_name,
                    'office_name': office_name,
                    'count': count,
                    'plan': plan_info.get('count', 0),
                    'is_high': plan_info.get('is_high', False)
                })
        
        for obj_name, plan_info in plans.items():
            already_added = any(s['object_name'] == obj_name and s['office_name'] in offices_stats.keys() 
                               for s in snapshots)
            if not already_added:
                snapshots.append({
                    'object_name': obj_name,
                    'office_name': 'complect',
                    'count': 0,
                    'plan': plan_info.get('count', 0),
                    'is_high': plan_info.get('is_high', False)
                })
        
        if snapshots:
            save_daily_snapshots_batch(date_key, snapshots)
        
        return jsonify({
            'success': True,
            'date': date_key,
            'snapshots_count': len(snapshots),
            'message': f'Снапшот за {date_key} успешно сохранён'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при генерации снапшота: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/snapshot/status', methods=['GET'])
def snapshot_status():
    """Проверяет, есть ли снапшоты за указанный период"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        from_date = request.args.get('from')
        to_date = request.args.get('to')
        
        if not from_date or not to_date:
            return jsonify({'error': 'Не указан период'}), 400
        
        from database import check_snapshot_exists
        
        start = datetime.strptime(from_date, '%Y-%m-%d')
        end = datetime.strptime(to_date, '%Y-%m-%d')
        
        missing_dates = []
        existing_dates = []
        
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            if check_snapshot_exists(date_str):
                existing_dates.append(date_str)
            else:
                missing_dates.append(date_str)
            current += timedelta(days=1)
        
        return jsonify({
            'existing_dates': existing_dates,
            'missing_dates': missing_dates,
            'total_days': len(existing_dates) + len(missing_dates),
            'existing_count': len(existing_dates),
            'missing_count': len(missing_dates)
        })
        
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса снапшотов: {e}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/snapshot/generate-range', methods=['POST'])
def generate_snapshot_range():
    """Генерирует снапшоты за диапазон дат"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        data = request.get_json()
        from_date = data.get('from')
        to_date = data.get('to')
        
        if not from_date or not to_date:
            return jsonify({'error': 'Не указан период'}), 400
        
        from database import get_plan_requirements_for_date, save_daily_snapshots_batch, delete_snapshots_for_date
        
        start = datetime.strptime(from_date, '%Y-%m-%d')
        end = datetime.strptime(to_date, '%Y-%m-%d')
        
        results = []
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            
            if current > datetime.now():
                results.append({
                    'date': date_str,
                    'status': 'skipped',
                    'message': 'Будущая дата'
                })
            else:
                try:
                    offices_stats = bitrix_api.get_all_offices_stats(current)
                    plans = get_plan_requirements_for_date(current)
                    
                    delete_snapshots_for_date(date_str)
                    
                    snapshots = []
                    for office_name, office_data in offices_stats.items():
                        for obj_name, count in office_data.get('objects', {}).items():
                            plan_info = plans.get(obj_name, {})
                            snapshots.append({
                                'object_name': obj_name,
                                'office_name': office_name,
                                'count': count,
                                'plan': plan_info.get('count', 0),
                                'is_high': plan_info.get('is_high', False)
                            })
                    
                    for obj_name, plan_info in plans.items():
                        already_added = any(s['object_name'] == obj_name for s in snapshots)
                        if not already_added:
                            snapshots.append({
                                'object_name': obj_name,
                                'office_name': 'complect',
                                'count': 0,
                                'plan': plan_info.get('count', 0),
                                'is_high': plan_info.get('is_high', False)
                            })
                    
                    if snapshots:
                        save_daily_snapshots_batch(date_str, snapshots)
                    
                    results.append({
                        'date': date_str,
                        'status': 'success',
                        'snapshots_count': len(snapshots)
                    })
                except Exception as e:
                    results.append({
                        'date': date_str,
                        'status': 'error',
                        'message': str(e)
                    })
            
            current += timedelta(days=1)
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(results),
            'success_count': len([r for r in results if r['status'] == 'success'])
        })
        
    except Exception as e:
        logger.error(f"Ошибка при генерации диапазона снапшотов: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ========== ОТЧЁТЫ ПО ОТРАБОТАВШИМ 1 СМЕНУ (ИЗ ТЕЛЕГРАМ БОТА) ==========

@dashboard_bp.route('/first-shift-by-object', methods=['GET'])
def get_first_shift_by_object():
    """
    Отчёт: отработавшие 1 смену по объектам (группировка по компаниям)
    Параметры: ?from=YYYY-MM-DD&to=YYYY-MM-DD
    """
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
        
        shift_api = ShiftReportAPI(BITRIX_WEBHOOK_URL)
        data = shift_api.get_shift_report(from_date, to_date)
        
        # Подсчёт итогов
        totals = {}
        for cat in ['Поток', 'Комплект', 'Бишкек']:
            cat_data = data.get(cat, {})
            totals[cat] = sum(cat_data.values()) if cat_data else 0
        
        total_all = sum(totals.values())
        
        return jsonify({
            'success': True,
            'from_date': from_date,
            'to_date': to_date,
            'data': data,
            'totals': totals,
            'total_all': total_all
        })
        
    except Exception as e:
        logger.error(f"Ошибка в get_first_shift_by_object: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/first-shift-by-staff', methods=['GET'])
def get_first_shift_by_staff():
    """
    Отчёт: отработавшие 1 смену по сотрудникам колл-центра
    Параметры: ?from=YYYY-MM-DD&to=YYYY-MM-DD
    """
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
        
        shift_api = ShiftReportAPI(BITRIX_WEBHOOK_URL)
        data = shift_api.get_staff_report(from_date, to_date)
        
        # Подсчёт итогов
        totals = {}
        for cat in ['Поток', 'Комплект', 'Бишкек']:
            cat_data = data.get(cat, {})
            totals[cat] = sum(cat_data.values()) if cat_data else 0
        
        total_all = sum(totals.values())
        
        return jsonify({
            'success': True,
            'from_date': from_date,
            'to_date': to_date,
            'data': data,
            'totals': totals,
            'total_all': total_all
        })
        
    except Exception as e:
        logger.error(f"Ошибка в get_first_shift_by_staff: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500