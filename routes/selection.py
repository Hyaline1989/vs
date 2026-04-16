# routes/selection.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
import logging
import sqlite3

from database import (
    get_objects_settings, update_object_settings, get_global_order, save_global_order,
    get_user_module_permissions, get_user_object_permissions, get_objects_settings_extended,
    get_plan_requirements_for_date, DB_NAME
)
from datetime import datetime

logger = logging.getLogger(__name__)

selection_bp = Blueprint('selection', __name__, url_prefix='/api/selection')

google_api = None

def init_selection_apis(google):
    global google_api
    google_api = google


@selection_bp.route('/settings')
@login_required
def selection_settings():
    """Получение настроек для подбора объектов"""
    try:
        # Получаем дату из запроса (если есть)
        date_param = request.args.get('date')
        if date_param:
            target_date = date_param
            logger.info(f"📅 Загрузка приоритетов за указанную дату: {target_date}")
        else:
            # Если дата не передана, используем сегодняшнюю
            target_date = datetime.now().strftime('%Y-%m-%d')
            logger.info(f"📅 Загрузка приоритетов за сегодня: {target_date}")
        
        db_objects = get_objects_settings_extended()
        db_objects = [obj for obj in db_objects if obj.get('visible', True)]
        
        objects_settings = get_objects_settings()
        global_order = get_global_order()
        
        if not global_order:
            global_order = [obj['id'] for obj in db_objects]
            save_global_order(global_order)
        
        # Получаем потребности за указанную дату
        requirements = get_plan_requirements_for_date(target_date)
        
        objects = []
        for db_obj in db_objects:
            setting = next((s for s in objects_settings if s['id'] == db_obj['id']), None)
            
            req_data = requirements.get(db_obj['name'], {})
            priority_from_req = req_data.get('is_high', False)
            
            objects.append({
                'id': db_obj['id'],
                'name': db_obj['name'],
                'ageMin': db_obj.get('ageMin', 18),
                'ageMax': db_obj.get('ageMax', 55),
                'allowedGenders': db_obj.get('allowedGenders', ['мужчина', 'женщина']),
                'allowedNationalities': db_obj.get('allowedNationalities', ['РФ']),
                'allowsConviction': db_obj.get('allowsConviction', False),
                'link': db_obj.get('link', ''),
                'visible': setting['visible'] if setting else True,
                'priority': priority_from_req,
                'requirement': req_data.get('count', 0)
            })
        
        if current_user.role != 'admin':
            object_perms = get_user_object_permissions(current_user.id)
            visible_object_ids = [obj_id for obj_id, perms in object_perms.items() if perms.get('selection', False)]
            objects = [obj for obj in objects if obj['id'] in visible_object_ids]
        
        return jsonify({
            'objects': objects,
            'globalOrder': global_order,
            'vacancyData': {}
        })
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек подбора: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@selection_bp.route('/order', methods=['POST'])
@login_required
def selection_order():
    """Сохранение порядка объектов"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    module_perms = get_user_module_permissions(current_user.id)
    if not module_perms.get('selection', False):
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        data = request.get_json()
        order = data.get('order', [])
        
        if order:
            save_global_order(order)
            return jsonify({'success': True})
        return jsonify({'error': 'Некорректный порядок'}), 400
    except Exception as e:
        logger.error(f"Ошибка сохранения порядка: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@selection_bp.route('/object/<int:object_id>', methods=['POST'])
@login_required
def selection_object(object_id):
    """Обновление настроек объекта (видимость, приоритет)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    module_perms = get_user_module_permissions(current_user.id)
    if not module_perms.get('selection', False):
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        data = request.get_json()
        visible = data.get('visible')
        priority = data.get('priority')
        
        if visible is not None and priority is not None:
            update_object_settings(object_id, visible, priority)
            return jsonify({'success': True})
        return jsonify({'error': 'Не указаны параметры'}), 400
    except Exception as e:
        logger.error(f"Ошибка обновления объекта: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@selection_bp.route('/debug/priority')
@login_required
def debug_priority():
    """Диагностический эндпоинт для проверки приоритетов"""
    if not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT vr.date, vo.name, vr.is_high
            FROM vacancy_requirements vr
            JOIN vacancy_positions vp ON vp.id = vr.position_id
            JOIN vacancy_objects vo ON vo.id = vp.object_id
            WHERE vr.is_high = 1
            ORDER BY vr.date DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        priority_dates = {}
        for row in rows:
            date = row[0]
            name = row[1]
            if date not in priority_dates:
                priority_dates[date] = []
            priority_dates[date].append(name)
        
        return jsonify({
            'priority_by_date': priority_dates
        })
    except Exception as e:
        logger.error(f"Ошибка диагностики приоритетов: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500