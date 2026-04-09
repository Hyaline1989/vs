# routes/selection.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
import logging

from database import (
    get_objects_settings, update_object_settings, get_global_order, save_global_order,
    get_user_module_permissions, get_user_object_permissions, get_all_max_requirements,
    get_objects_settings_extended  # ДОБАВЛЕНО: для получения полных данных из БД
)
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
        # ЗАГРУЖАЕМ ОБЪЕКТЫ ИЗ БАЗЫ ДАННЫХ (вместо OBJECTS_BASE)
        db_objects = get_objects_settings_extended()
        
        # Оставляем только видимые объекты
        db_objects = [obj for obj in db_objects if obj.get('visible', True)]
        
        objects_settings = get_objects_settings()
        global_order = get_global_order()
        
        # Если нет сохранённого порядка, создаём из ID объектов в БД
        if not global_order:
            global_order = [obj['id'] for obj in db_objects]
            save_global_order(global_order)
        
        # Получаем приоритеты и потребности из базы данных за сегодня
        today = datetime.now()
        today_requirements = get_all_max_requirements(today)
        
        # Создаём словарь для быстрого поиска потребностей по нормализованным названиям
        from normalizer import ObjectNameNormalizer
        normalizer = ObjectNameNormalizer()
        
        req_by_normalized = {}
        for req_name, req_data in today_requirements.items():
            normalized = normalizer.normalize(req_name)
            req_by_normalized[normalized] = req_data
        
        objects = []
        for db_obj in db_objects:
            setting = next((s for s in objects_settings if s['id'] == db_obj['id']), None)
            
            # Нормализуем название объекта
            normalized_obj_name = normalizer.normalize(db_obj['name'])
            
            # Получаем потребность из БД
            req_data = req_by_normalized.get(normalized_obj_name, {})
            requirement_count = req_data.get('count', 0)
            db_priority = req_data.get('is_high', False)
            
            if requirement_count > 0:
                logger.debug(f"Объект {db_obj['name']}: потребность={requirement_count}, приоритет={db_priority}")
            
            # Используем данные из БД
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
                'priority': db_priority,  # Приоритет из БД потребностей
                'requirement': requirement_count  # Добавляем текущую потребность
            })
        
        logger.info(f"Загружено {len(objects)} объектов из БД, из них приоритетных: {sum(1 for o in objects if o['priority'])}, с потребностями: {sum(1 for o in objects if o['requirement'] > 0)}")
        
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