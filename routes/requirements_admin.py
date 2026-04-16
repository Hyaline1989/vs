# routes/requirements_admin.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import logging
from database import (
    get_all_vacancy_data,
    save_vacancy_object,
    delete_vacancy_object,
    save_vacancy_position,
    delete_vacancy_position,
    save_vacancy_requirements_batch,
    init_vacancy_tables
)

logger = logging.getLogger(__name__)

requirements_admin_bp = Blueprint('requirements_admin', __name__, url_prefix='/api/requirements')

# Инициализируем таблицы при загрузке модуля
init_vacancy_tables()


@requirements_admin_bp.route('/vacancy', methods=['GET'])
@login_required
def get_vacancy():
    """Получение всех данных о вакансиях за указанную дату"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role not in ['admin', 'manager']:
        if not current_user.can_view_selection():
            return jsonify({'error': 'Forbidden'}), 403
    
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        data = get_all_vacancy_data(date_str)
        return jsonify({
            'date': date_str,
            'data': data
        })
    except Exception as e:
        logger.error(f"Ошибка получения вакансий: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@requirements_admin_bp.route('/object', methods=['POST'])
@login_required
def create_object():
    """Создание нового объекта вакансии"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Название объекта обязательно'}), 400
    
    obj_id = save_vacancy_object(name)
    
    if obj_id:
        from database import log_user_action
        log_user_action(current_user.id, 'create_vacancy_object', f"Создан объект вакансии: {name}", request.remote_addr)
        return jsonify({'success': True, 'id': obj_id})
    else:
        return jsonify({'error': 'Ошибка создания или объект уже существует'}), 400


@requirements_admin_bp.route('/object/<string:name>', methods=['DELETE'])
@login_required
def delete_object(name):
    """Удаление объекта вакансии"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    if delete_vacancy_object(name):
        from database import log_user_action
        log_user_action(current_user.id, 'delete_vacancy_object', f"Удалён объект вакансии: {name}", request.remote_addr)
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Объект не найден'}), 404


@requirements_admin_bp.route('/position', methods=['POST'])
@login_required
def create_position():
    """Добавление должности к объекту"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    object_name = data.get('object_name', '').strip()
    position_name = data.get('position_name', '').strip()
    
    if not object_name or not position_name:
        return jsonify({'error': 'Название объекта и должности обязательны'}), 400
    
    pos_id = save_vacancy_position(object_name, position_name)
    
    if pos_id:
        from database import log_user_action
        log_user_action(current_user.id, 'create_vacancy_position', 
                       f"Добавлена должность {position_name} к объекту {object_name}", 
                       request.remote_addr)
        return jsonify({'success': True, 'id': pos_id})
    else:
        return jsonify({'error': 'Ошибка создания или должность уже существует'}), 400


@requirements_admin_bp.route('/position', methods=['DELETE'])
@login_required
def delete_position():
    """Удаление должности"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    object_name = data.get('object_name', '').strip()
    position_name = data.get('position_name', '').strip()
    
    if not object_name or not position_name:
        return jsonify({'error': 'Название объекта и должности обязательны'}), 400
    
    if delete_vacancy_position(object_name, position_name):
        from database import log_user_action
        log_user_action(current_user.id, 'delete_vacancy_position', 
                       f"Удалена должность {position_name} из объекта {object_name}", 
                       request.remote_addr)
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Должность не найдена'}), 404


@requirements_admin_bp.route('/save-all', methods=['POST'])
@login_required
def save_all_requirements():
    """Сохранение всех данных о вакансиях"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    objects_data = data.get('objects', {})
    
    saved_count = 0
    
    for obj_name, obj_data in objects_data.items():
        # Добавляем флаг is_high из приоритета объекта
        is_high = obj_data.get('is_high', False)
        for pos in obj_data.get('positions', []):
            pos['is_high'] = is_high
        
        if save_vacancy_requirements_batch(obj_name, date, obj_data.get('positions', [])):
            saved_count += 1
    
    from database import log_user_action
    log_user_action(current_user.id, 'save_vacancy_requirements', 
                   f"Сохранены вакансии за {date}: {saved_count} объектов", 
                   request.remote_addr)
    
    return jsonify({
        'success': True,
        'saved_objects': saved_count
    })


@requirements_admin_bp.route('/migrate', methods=['POST'])
@login_required
def migrate_from_sheets():
    """Миграция данных из Google Sheets (одноразовая)"""
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        from database import migrate_from_google_sheets
        success = migrate_from_google_sheets()
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Ошибка миграции: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@requirements_admin_bp.route('/ensure-data', methods=['POST'])
@login_required
def ensure_data_exists():
    """Автоматически копирует данные с предыдущего дня, если за текущий нет"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        from database import copy_requirements_from_previous_day
        copied_count = copy_requirements_from_previous_day(date)
        
        return jsonify({
            'success': True,
            'copied': copied_count,
            'date': date,
            'message': f'Скопировано {copied_count} записей' if copied_count > 0 else 'Нет данных для копирования'
        })
    except Exception as e:
        logger.error(f"Ошибка автопереноса: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500