# routes/selection.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
import logging

from database import (
    get_objects_settings, update_object_settings, get_global_order, save_global_order,
    get_user_module_permissions, get_user_object_permissions, get_all_max_requirements
)
from config import OBJECTS_BASE
from datetime import datetime

logger = logging.getLogger(__name__)

# Создаём blueprint для подбора объектов
selection_bp = Blueprint('selection', __name__, url_prefix='/api/selection')

# Google Sheets API (будет переопределено в app.py)
google_api = None

def init_selection_apis(google):
    """Инициализирует API для selection blueprint"""
    global google_api
    google_api = google


@selection_bp.route('/settings')
@login_required
def selection_settings():
    """Получение настроек для подбора объектов"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        objects_settings = get_objects_settings()
        global_order = get_global_order()
        
        if not global_order:
            global_order = [obj['id'] for obj in OBJECTS_BASE]
            save_global_order(global_order)
        
        # Получаем приоритеты из базы данных потребностей за сегодня
        today = datetime.now()
        today_requirements = get_all_max_requirements(today)
        
        objects = []
        for base_obj in OBJECTS_BASE:
            setting = next((s for s in objects_settings if s['id'] == base_obj['id']), None)
            
            # Получаем приоритет из базы данных потребностей
            db_priority = False
            for req_name, req_data in today_requirements.items():
                # Нормализуем название для сравнения
                from normalizer import ObjectNameNormalizer
                normalizer = ObjectNameNormalizer()
                normalized_obj_name = normalizer.normalize(base_obj['name'])
                normalized_req_name = normalizer.normalize(req_name)
                
                if normalized_obj_name == normalized_req_name:
                    db_priority = req_data.get('is_high', False)
                    logger.info(f"Объект {base_obj['name']} имеет приоритет из БД: {db_priority}")
                    break
            
            objects.append({
                'id': base_obj['id'],
                'name': base_obj['name'],
                'ageMin': base_obj['ageMin'],
                'ageMax': base_obj['ageMax'],
                'allowedGenders': base_obj['allowedGenders'],
                'allowedNationalities': base_obj['allowedNationalities'],
                'allowsConviction': base_obj['allowsConviction'],
                'link': base_obj['link'],
                'visible': setting['visible'] if setting else True,
                'priority': db_priority  # Используем приоритет из БД потребностей
            })
        
        logger.info(f"Загружено {len(objects)} объектов, из них приоритетных: {sum(1 for o in objects if o['priority'])}")
        
        # Фильтрация по правам для подбора объектов
        if current_user.role != 'admin':
            object_perms = get_user_object_permissions(current_user.id)
            visible_object_ids = [obj_id for obj_id, perms in object_perms.items() if perms.get('selection', False)]
            objects = [obj for obj in objects if obj['id'] in visible_object_ids]
            logger.info(f"Пользователь {current_user.username} видит {len(objects)} объектов в подборе")
        
        vacancy_data = google_api.get_vacancy_data() if google_api else {}
        
        return jsonify({
            'objects': objects,
            'globalOrder': global_order,
            'vacancyData': vacancy_data
        })
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек подбора: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@selection_bp.route('/order', methods=['POST'])
@login_required
def selection_order():
    """Сохранение порядка объектов"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
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
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
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
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        today = datetime.now()
        today_requirements = get_all_max_requirements(today)
        
        result = {
            'date': today.strftime('%Y-%m-%d'),
            'requirements_count': len(today_requirements),
            'priority_objects': []
        }
        
        for name, data in today_requirements.items():
            if data.get('is_high', False):
                result['priority_objects'].append({
                    'name': name,
                    'count': data['count'],
                    'is_high': data['is_high']
                })
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Ошибка диагностики приоритетов: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500