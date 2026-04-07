# routes/objects_admin.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_login import current_user
import logging

from database import (
    get_objects_settings, update_object_settings, 
    get_object_by_id, create_object, delete_object,
    get_objects_base, get_global_order, save_global_order
)
from config import OBJECTS_BASE

logger = logging.getLogger(__name__)

objects_admin_bp = Blueprint('objects_admin', __name__, url_prefix='/api/admin/objects')


@objects_admin_bp.route('', methods=['GET'])
def get_objects():
    """Получение списка всех объектов с настройками"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    objects = get_objects_settings()
    
    # Добавляем полную информацию из OBJECTS_BASE
    base_dict = {obj['id']: obj for obj in OBJECTS_BASE}
    for obj in objects:
        if obj['id'] in base_dict:
            obj.update(base_dict[obj['id']])
    
    return jsonify({
        'objects': objects,
        'base_objects': OBJECTS_BASE
    })


@objects_admin_bp.route('/<int:object_id>', methods=['GET'])
def get_object(object_id):
    """Получение информации об объекте"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    obj = get_object_by_id(object_id)
    if not obj:
        return jsonify({'error': 'Объект не найден'}), 404
    
    return jsonify(obj)


@objects_admin_bp.route('', methods=['POST'])
def create_object_api():
    """Создание нового объекта"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    
    # Валидация обязательных полей
    required_fields = ['name', 'ageMin', 'ageMax', 'allowedGenders', 'allowedNationalities']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Поле {field} обязательно'}), 400
    
    # Валидация числовых полей
    try:
        age_min = int(data['ageMin'])
        age_max = int(data['ageMax'])
        if age_min < 18 or age_min > 100:
            return jsonify({'error': 'Минимальный возраст должен быть от 18 до 100'}), 400
        if age_max < age_min:
            return jsonify({'error': 'Максимальный возраст должен быть больше минимального'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Возраст должен быть числом'}), 400
    
    # Валидация списков
    allowed_genders = data.get('allowedGenders', [])
    if not isinstance(allowed_genders, list) or not allowed_genders:
        return jsonify({'error': 'Укажите допустимые полы'}), 400
    
    allowed_nationalities = data.get('allowedNationalities', [])
    if not isinstance(allowed_nationalities, list) or not allowed_nationalities:
        return jsonify({'error': 'Укажите допустимые гражданства'}), 400
    
    allows_conviction = bool(data.get('allowsConviction', False))
    link = data.get('link', '')
    visible = bool(data.get('visible', True))
    priority = bool(data.get('priority', False))
    
    # Создаём объект
    object_id = create_object(
        name=data['name'],
        age_min=age_min,
        age_max=age_max,
        allowed_genders=allowed_genders,
        allowed_nationalities=allowed_nationalities,
        allows_conviction=allows_conviction,
        link=link,
        visible=visible,
        priority=priority
    )
    
    if not object_id:
        return jsonify({'error': 'Ошибка при создании объекта (возможно, такое имя уже существует)'}), 500
    
    from database import log_user_action
    log_user_action(current_user.id, 'create_object', f"Создан объект {data['name']} (ID: {object_id})", request.remote_addr)
    
    return jsonify({'success': True, 'object_id': object_id})


@objects_admin_bp.route('/<int:object_id>', methods=['PUT'])
def update_object_api(object_id):
    """Обновление объекта"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    
    # Подготавливаем данные для обновления
    updates = {}
    
    if 'name' in data:
        updates['name'] = data['name']
    
    if 'ageMin' in data:
        try:
            age_min = int(data['ageMin'])
            if age_min < 18 or age_min > 100:
                return jsonify({'error': 'Минимальный возраст должен быть от 18 до 100'}), 400
            updates['age_min'] = age_min
        except (ValueError, TypeError):
            return jsonify({'error': 'Возраст должен быть числом'}), 400
    
    if 'ageMax' in data:
        try:
            age_max = int(data['ageMax'])
            updates['age_max'] = age_max
        except (ValueError, TypeError):
            return jsonify({'error': 'Возраст должен быть числом'}), 400
    
    if 'allowedGenders' in data:
        if not isinstance(data['allowedGenders'], list) or not data['allowedGenders']:
            return jsonify({'error': 'Укажите допустимые полы'}), 400
        updates['allowed_genders'] = data['allowedGenders']
    
    if 'allowedNationalities' in data:
        if not isinstance(data['allowedNationalities'], list) or not data['allowedNationalities']:
            return jsonify({'error': 'Укажите допустимые гражданства'}), 400
        updates['allowed_nationalities'] = data['allowedNationalities']
    
    if 'allowsConviction' in data:
        updates['allows_conviction'] = bool(data['allowsConviction'])
    
    if 'link' in data:
        updates['link'] = data['link']
    
    if 'visible' in data:
        updates['visible'] = bool(data['visible'])
    
    if 'priority' in data:
        updates['priority'] = bool(data['priority'])
    
    if not updates:
        return jsonify({'error': 'Нет данных для обновления'}), 400
    
    # Проверяем, что возраст min <= max
    if 'age_min' in updates and 'age_max' in updates:
        if updates['age_min'] > updates['age_max']:
            return jsonify({'error': 'Минимальный возраст не может быть больше максимального'}), 400
    
    success = update_object_settings(object_id, updates)
    
    if not success:
        return jsonify({'error': 'Ошибка при обновлении объекта'}), 500
    
    from database import log_user_action
    log_user_action(current_user.id, 'update_object', f"Обновлён объект ID {object_id}", request.remote_addr)
    
    return jsonify({'success': True})


@objects_admin_bp.route('/<int:object_id>', methods=['DELETE'])
def delete_object_api(object_id):
    """Удаление объекта"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    # Проверяем, существует ли объект
    obj = get_object_by_id(object_id)
    if not obj:
        return jsonify({'error': 'Объект не найден'}), 404
    
    # Не даём удалить объекты из базовой конфигурации (первые 23)
    if object_id <= len(OBJECTS_BASE):
        return jsonify({'error': 'Нельзя удалить базовый объект из конфигурации'}), 400
    
    success = delete_object(object_id)
    
    if not success:
        return jsonify({'error': 'Ошибка при удалении объекта'}), 500
    
    from database import log_user_action
    log_user_action(current_user.id, 'delete_object', f"Удалён объект {obj['name']} (ID: {object_id})", request.remote_addr)
    
    return jsonify({'success': True})


@objects_admin_bp.route('/order', methods=['GET'])
def get_order():
    """Получение порядка объектов"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    order = get_global_order()
    return jsonify({'order': order or []})


@objects_admin_bp.route('/order', methods=['POST'])
def save_order():
    """Сохранение порядка объектов"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    order = data.get('order', [])
    
    if not isinstance(order, list):
        return jsonify({'error': 'Некорректный формат порядка'}), 400
    
    success = save_global_order(order)
    
    if not success:
        return jsonify({'error': 'Ошибка при сохранении порядка'}), 500
    
    from database import log_user_action
    log_user_action(current_user.id, 'save_order', f"Сохранён порядок объектов ({len(order)} объектов)", request.remote_addr)
    
    return jsonify({'success': True})