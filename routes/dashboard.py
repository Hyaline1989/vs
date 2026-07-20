# routes/dashboard.py - добавлен эндпоинт для фиксации дня
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, redirect
from flask_login import current_user, login_required
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
        if (now - _cache_timestamps[cache_key]).total_seconds() < CACHE_DURATION:
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


def get_date_range(start, end):
    """Возвращает список дат в формате YYYY-MM-DD для закрытого периода."""
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    return dates


def load_plans_by_date(from_date, to_date):
    """Загружает плановые потребности из БД за период."""
    plans_by_date = {}

    with sqlite3.connect(DB_NAME) as conn:
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

    for row in plan_rows:
        date_key = row['date']
        obj_name = row['name']

        if date_key not in plans_by_date:
            plans_by_date[date_key] = {}

        plans_by_date[date_key][obj_name] = {
            'plan': row['total_plan'] or 0,
            'is_high': bool(row['is_high'])
        }

    return plans_by_date


def build_report_result(dates_list, plans_by_date, facts_by_date):
    """Собирает итоговый JSON отчёта из планов и факта."""
    result = []

    for date_key in dates_list:
        date_plans = plans_by_date.get(date_key, {})
        date_facts = facts_by_date.get(date_key, {})
        all_objects = set(date_plans.keys()) | set(date_facts.keys())

        day_data = {
            'date': datetime.strptime(date_key, '%Y-%m-%d').strftime('%d.%m.%Y'),
            'objects': {}
        }

        has_any_data = False
        for obj_name in sorted(all_objects):
            plan_info = date_plans.get(obj_name, {'plan': 0, 'is_high': False})
            fact_info = date_facts.get(obj_name, {})

            total_sent = (
                fact_info.get('complect', 0) +
                fact_info.get('potok', 0) +
                fact_info.get('gorkiy', 0) +
                fact_info.get('agent', 0) +
                fact_info.get('bishkek', 0)
            )

            if plan_info['plan'] == 0 and total_sent == 0:
                continue

            day_data['objects'][obj_name] = {
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

    return result


def build_report_from_snapshots(from_date, to_date):
    """Формирует отчёт из ежедневных снапшотов."""
    from database import get_snapshot_report

    snapshots_data = get_snapshot_report(from_date, to_date)
    result = []

    for date_key, objects in snapshots_data.items():
        day_data = {
            'date': datetime.strptime(date_key, '%Y-%m-%d').strftime('%d.%m.%Y'),
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

    return result


def all_snapshots_exist(dates_list):
    """Проверяет наличие снапшотов за все даты периода."""
    from database import check_snapshot_exists

    for date_key in dates_list:
        if not check_snapshot_exists(date_key):
            return False
    return True


def convert_report_facts_to_offices(facts_for_date):
    """Преобразует факт отчёта в структуру офисов для генерации снапшота."""
    offices = {
        'complect': {'count': 0, 'objects': {}},
        'potok': {'count': 0, 'objects': {}},
        'gorkiy52': {'count': 0, 'objects': {}},
        'agent': {'count': 0, 'objects': {}},
        'bishkek': {'count': 0, 'objects': {}}
    }

    office_mapping = {
        'complect': 'complect',
        'potok': 'potok',
        'gorkiy': 'gorkiy52',
        'agent': 'agent',
        'bishkek': 'bishkek'
    }

    for object_name, counts in facts_for_date.items():
        for report_key, office_name in office_mapping.items():
            count = counts.get(report_key, 0)
            if not count:
                continue
            offices[office_name]['objects'][object_name] = count
            offices[office_name]['count'] += count

    return offices


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
        
        # Загружаем сделки за день одним проходом. Раньше статистика офисов и
        # сравнение план/факт повторно запрашивали одни и те же данные из Bitrix,
        # из-за чего обработчик мог не уложиться в таймаут веб-сервера.
        cache_key = f"dashboard_facts_{date_str}"
        facts_by_date = get_cached_data(
            cache_key,
            bitrix_api.get_report_facts_range,
            date_str,
            date_str
        )
        facts_for_date = facts_by_date.get(date_str, {})
        offices_stats = convert_report_facts_to_offices(facts_for_date)

        total_facts = {
            object_name: sum(office_counts.values())
            for object_name, office_counts in facts_for_date.items()
        }
        comparison = comparer.compare_by_date(target_date, deals=total_facts)
        
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
    """
    Оптимизированный отчёт по плану/факту.

    Если за весь период есть снапшоты — отдаём данные из БД.
    Если снапшотов нет или они неполные — забираем факт из Bitrix
    одним диапазонным запросом вместо цикла по дням и офисам.
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

        try:
            start = datetime.strptime(from_date, '%Y-%m-%d')
            end = datetime.strptime(to_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Неверный формат даты'}), 400

        if start > end:
            return jsonify({'error': 'Дата начала не может быть позже даты окончания'}), 400

        dates_list = get_date_range(start, end)

        if all_snapshots_exist(dates_list):
            logger.info("Отчёт из снапшотов за %s - %s", from_date, to_date)
            return jsonify(build_report_from_snapshots(from_date, to_date))

        if bitrix_api is None:
            logger.error("Bitrix API не инициализирован")
            return jsonify({'error': 'Bitrix API не инициализирован'}), 500

        logger.warning(
            "Снапшоты отсутствуют не за все даты периода %s - %s. "
            "Используем диапазонный запрос к Bitrix.",
            from_date,
            to_date
        )

        plans_by_date = load_plans_by_date(from_date, to_date)
        cache_key = f"report_range_{from_date}_{to_date}"
        facts_by_date = get_cached_data(
            cache_key,
            bitrix_api.get_report_facts_range,
            from_date,
            to_date
        )

        result = build_report_result(dates_list, plans_by_date, facts_by_date)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Ошибка при формировании отчёта: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ========== НОВЫЙ ЭНДПОИНТ: ФИКСАЦИЯ ДНЯ В ОТЧЁТЕ ==========

@dashboard_bp.route('/fix-day', methods=['POST'])
@login_required
def fix_day():
    """
    Фиксирует день в отчёте:
    1. Обновляет приоритеты (is_high) в vacancy_requirements для выбранной даты
    2. Берёт текущие приоритеты из current_requirements
    3. Генерирует снапшот за указанную дату с этими приоритетами
    4. Сохраняет снапшот в БД
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Только администратор может фиксировать дни
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden', 'message': 'Только администратор может фиксировать дни'}), 403
    
    try:
        data = request.get_json() or {}
        date_str = data.get('date')
        
        if not date_str:
            return jsonify({'error': 'Не указана дата'}), 400
        
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return jsonify({'error': 'Неверный формат даты'}), 400
        
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        date_key = target_date.strftime('%Y-%m-%d')
        
        logger.info(f"🔄 Фиксация дня {date_key} пользователем {current_user.username}")
        
        from database import (
            get_current_requirements,
            get_plan_requirements_for_date,
            save_daily_snapshots_batch,
            delete_snapshots_for_date,
            DB_NAME
        )
        
        # 1. Получаем текущие приоритеты из current_requirements
        current_req = get_current_requirements()
        priorities = {}
        for obj_name, obj_data in current_req.items():
            if obj_data.get('is_high', False):
                priorities[obj_name] = True
                logger.info(f"🔴 Приоритетный объект: {obj_name}")
        
        # 2. ОБНОВЛЯЕМ ПРИОРИТЕТЫ В vacancy_requirements ДЛЯ ДАШБОРДА
        #    Это нужно, чтобы в Дашборде (план/факт) отображался приоритет
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            # Для каждого приоритетного объекта обновляем is_high в vacancy_requirements
            for obj_name, is_high in priorities.items():
                if is_high:
                    # Находим все position_id для этого объекта
                    cursor.execute('''
                        SELECT vp.id FROM vacancy_positions vp
                        JOIN vacancy_objects vo ON vo.id = vp.object_id
                        WHERE vo.name = ?
                    ''', (obj_name,))
                    position_ids = [row[0] for row in cursor.fetchall()]
                    
                    if position_ids:
                        # Обновляем is_high для всех позиций этого объекта на указанную дату
                        placeholders = ','.join(['?'] * len(position_ids))
                        cursor.execute(f'''
                            UPDATE vacancy_requirements 
                            SET is_high = 1, updated_at = CURRENT_TIMESTAMP
                            WHERE position_id IN ({placeholders}) AND date = ?
                        ''', position_ids + [date_key])
                        logger.info(f"✅ Обновлён приоритет для объекта {obj_name} в vacancy_requirements на дату {date_key}")
            
            # Также сбрасываем приоритеты для объектов, у которых нет приоритета в current_requirements
            # Находим все объекты, у которых есть записи в vacancy_requirements за эту дату
            cursor.execute('''
                SELECT DISTINCT vo.name 
                FROM vacancy_requirements vr
                JOIN vacancy_positions vp ON vp.id = vr.position_id
                JOIN vacancy_objects vo ON vo.id = vp.object_id
                WHERE vr.date = ?
            ''', (date_key,))
            all_objects_in_db = [row[0] for row in cursor.fetchall()]
            
            for obj_name in all_objects_in_db:
                if obj_name not in priorities or not priorities[obj_name]:
                    # Сбрасываем приоритет для этого объекта
                    cursor.execute('''
                        SELECT vp.id FROM vacancy_positions vp
                        JOIN vacancy_objects vo ON vo.id = vp.object_id
                        WHERE vo.name = ?
                    ''', (obj_name,))
                    position_ids = [row[0] for row in cursor.fetchall()]
                    
                    if position_ids:
                        placeholders = ','.join(['?'] * len(position_ids))
                        cursor.execute(f'''
                            UPDATE vacancy_requirements 
                            SET is_high = 0, updated_at = CURRENT_TIMESTAMP
                            WHERE position_id IN ({placeholders}) AND date = ?
                        ''', position_ids + [date_key])
                        logger.info(f"✅ Сброшен приоритет для объекта {obj_name} в vacancy_requirements на дату {date_key}")
            
            conn.commit()
            logger.info(f"✅ Приоритеты обновлены в vacancy_requirements для даты {date_key}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при обновлении приоритетов в vacancy_requirements: {e}")
            return jsonify({'error': f'Ошибка обновления приоритетов: {str(e)}'}), 500
        finally:
            conn.close()
        
        # 3. Получаем план (потребности) за указанную дату
        plans = get_plan_requirements_for_date(target_date)
        
        # 4. Получаем фактические данные из Bitrix за указанную дату
        offices_stats = bitrix_api.get_all_offices_stats(target_date)
        
        # 5. Удаляем старый снапшот за эту дату (если есть)
        delete_snapshots_for_date(date_key)
        
        # 6. Формируем новые снапшоты (используем обновлённые приоритеты)
        snapshots = []
        
        # Добавляем данные по офисам
        for office_name, office_data in offices_stats.items():
            for obj_name, count in office_data.get('objects', {}).items():
                plan_info = plans.get(obj_name, {})
                # Проверяем, есть ли у объекта приоритет
                is_high = priorities.get(obj_name, False)
                
                snapshots.append({
                    'object_name': obj_name,
                    'office_name': office_name,
                    'count': count,
                    'plan': plan_info.get('count', 0),
                    'is_high': is_high
                })
        
        # Добавляем объекты из плана, которых нет в факте
        for obj_name, plan_info in plans.items():
            already_added = any(s['object_name'] == obj_name for s in snapshots)
            if not already_added:
                is_high = priorities.get(obj_name, False)
                snapshots.append({
                    'object_name': obj_name,
                    'office_name': 'complect',
                    'count': 0,
                    'plan': plan_info.get('count', 0),
                    'is_high': is_high
                })
        
        # 7. Сохраняем снапшоты
        if snapshots:
            save_daily_snapshots_batch(date_key, snapshots)
            logger.info(f"✅ Снапшот за {date_key} сохранён ({len(snapshots)} записей)")
            
            # Логируем действие
            from database import log_user_action
            log_user_action(
                current_user.id,
                'fix_day_in_report',
                f"Зафиксирован день {date_key} в отчёте (приоритетов: {len([s for s in snapshots if s['is_high']])})",
                request.remote_addr
            )
            
            # Очищаем кэш, чтобы Дашборд показал обновлённые данные
            clear_cache()
            
            return jsonify({
                'success': True,
                'date': date_key,
                'snapshots_count': len(snapshots),
                'priority_count': len([s for s in snapshots if s['is_high']]),
                'message': f'День {date_key} зафиксирован в отчёте. Приоритеты обновлены в Дашборде.'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Нет данных для сохранения'
            }), 400
        
    except Exception as e:
        logger.error(f"Ошибка при фиксации дня: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ========== ЭНДПОИНТЫ ДЛЯ УПРАВЛЕНИЯ СНАПШОТАМИ ==========

@dashboard_bp.route('/snapshot/generate', methods=['POST'])
@login_required
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
@login_required
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
@login_required
def generate_snapshot_range():
    """Генерирует снапшоты за диапазон дат одним диапазонным запросом к Bitrix."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401

    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403

    try:
        data = request.get_json() or {}
        from_date = data.get('from')
        to_date = data.get('to')

        if not from_date or not to_date:
            return jsonify({'error': 'Не указан период'}), 400

        try:
            start = datetime.strptime(from_date, '%Y-%m-%d')
            end = datetime.strptime(to_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Неверный формат даты'}), 400

        if start > end:
            return jsonify({'error': 'Дата начала не может быть позже даты окончания'}), 400

        if bitrix_api is None:
            logger.error("Bitrix API не инициализирован")
            return jsonify({'error': 'Bitrix API не инициализирован'}), 500

        from database import (
            get_plan_requirements_for_date,
            save_daily_snapshots_batch,
            delete_snapshots_for_date
        )

        now = datetime.now()
        fact_end = min(end, now)
        facts_by_date = {}

        if start <= fact_end:
            facts_by_date = bitrix_api.get_report_facts_range(
                start.strftime('%Y-%m-%d'),
                fact_end.strftime('%Y-%m-%d')
            )

        results = []
        current = start

        while current <= end:
            date_str = current.strftime('%Y-%m-%d')

            if current > now:
                results.append({
                    'date': date_str,
                    'status': 'skipped',
                    'message': 'Будущая дата'
                })
                current += timedelta(days=1)
                continue

            try:
                plans = get_plan_requirements_for_date(current)
                facts_for_date = facts_by_date.get(date_str, {})
                offices_stats = convert_report_facts_to_offices(facts_for_date)

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
                    already_added = any(
                        snapshot['object_name'] == obj_name
                        for snapshot in snapshots
                    )
                    if already_added:
                        continue

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
                logger.error(
                    "Ошибка при генерации снапшота за %s: %s",
                    date_str,
                    e,
                    exc_info=True
                )
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
@login_required
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
@login_required
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
