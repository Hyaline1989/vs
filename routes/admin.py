# routes/admin.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_login import current_user
from werkzeug.security import generate_password_hash
import logging

from database import (
    get_all_users, get_user_by_id, create_user, update_user, hard_delete_user,
    get_user_module_permissions, get_user_object_permissions,
    set_user_module_permission, set_user_object_permission, grant_all_objects_access,
    log_user_action
)

logger = logging.getLogger(__name__)

# Создаём blueprint для админ-функций
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


# ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ==========

@admin_bp.route('/users', methods=['GET'])
def get_users():
    """Получение списка пользователей"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    users = get_all_users()
    
    if current_user.role == 'manager':
        users = [u for u in users if u['role'] == 'viewer']
    elif current_user.role == 'admin' and current_user.id != 1:
        users = [u for u in users if u['id'] != 1]
    
    return jsonify(users)


@admin_bp.route('/users', methods=['POST'])
def create_user_api():
    """Создание нового пользователя"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '')
    email = data.get('email', '')
    role = data.get('role', 'viewer')
    
    if not username or not password:
        return jsonify({'error': 'Имя пользователя и пароль обязательны'}), 400
    if len(password) < 4:
        return jsonify({'error': 'Пароль должен быть не менее 4 символов'}), 400
    if role not in ['admin', 'manager', 'viewer']:
        return jsonify({'error': 'Некорректная роль'}), 400
    
    from database import get_user_by_username
    existing = get_user_by_username(username)
    if existing:
        return jsonify({'error': 'Пользователь с таким именем уже существует'}), 400
    
    if role == 'admin' and current_user.id != 1:
        return jsonify({'error': 'Только системный администратор может создавать администраторов'}), 403
    
    password_hash = generate_password_hash(password)
    user_id = create_user(username, password_hash, full_name, email, role, current_user.id)
    
    if not user_id:
        return jsonify({'error': 'Ошибка при создании пользователя'}), 500
    
    # Даём базовые права на модули
    set_user_module_permission(user_id, 'dashboard', True)
    set_user_module_permission(user_id, 'selection', True)
    
    if role == 'admin':
        grant_all_objects_access(user_id, True, True)
    
    log_user_action(current_user.id, 'create_user', f"Создан пользователь {username} (ID: {user_id})", request.remote_addr)
    
    return jsonify({'success': True, 'user_id': user_id})


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Получение информации о пользователе"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_data = get_user_by_id(user_id)
    if not user_data:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    module_perms = get_user_module_permissions(user_id)
    object_perms = get_user_object_permissions(user_id)
    
    return jsonify({
        'id': user_data['id'],
        'username': user_data['username'],
        'full_name': user_data['full_name'],
        'email': user_data['email'],
        'role': user_data['role'],
        'is_active': user_data['is_active'],
        'created_at': user_data['created_at'],
        'last_login': user_data['last_login'],
        'module_permissions': module_perms,
        'object_permissions': object_perms
    })


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
def update_user_api(user_id):
    """Обновление пользователя"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    user_data = get_user_by_id(user_id)
    if not user_data:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    updates = {}
    
    if current_user.id == user_id or current_user.role == 'admin':
        if 'full_name' in data:
            updates['full_name'] = data['full_name']
        if 'email' in data:
            updates['email'] = data['email']
        if 'is_active' in data and current_user.id != user_id:
            updates['is_active'] = data['is_active']
        if 'password' in data and data['password']:
            if len(data['password']) >= 4:
                updates['password_hash'] = generate_password_hash(data['password'])
            else:
                return jsonify({'error': 'Пароль должен быть не менее 4 символов'}), 400
    
    if updates:
        update_user(user_id, updates)
        log_user_action(current_user.id, 'update_user', f"Обновлён пользователь ID {user_id}", request.remote_addr)
    
    return jsonify({'success': True})


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user_api(user_id):
    """Удаление пользователя"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя удалить самого себя'}), 400
    
    target_user = get_user_by_id(user_id)
    if not target_user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    if target_user['role'] == 'admin' and current_user.id != 1:
        return jsonify({'error': 'Только системный администратор может удалять администраторов'}), 403
    if user_id == 1:
        return jsonify({'error': 'Нельзя удалить системного администратора'}), 403
    
    hard_delete_user(user_id)
    log_user_action(current_user.id, 'delete_user', f"Удалён пользователь ID {user_id}", request.remote_addr)
    return jsonify({'success': True})


# ========== УПРАВЛЕНИЕ ПРАВАМИ ==========

@admin_bp.route('/permissions/modules/<int:user_id>', methods=['GET'])
def get_user_module_perms(user_id):
    """Получение прав пользователя на модули"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    # Разрешаем пользователю просматривать свои собственные права
    if user_id == current_user.id:
        perms = get_user_module_permissions(user_id)
        return jsonify(perms)
    
    # Для manager: проверяем, что он запрашивает права только для viewer
    if current_user.role == 'manager':
        target_user = get_user_by_id(user_id)
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        if target_user['role'] != 'viewer':
            logger.warning(f"Manager {current_user.id} пытается получить права модулей пользователя {user_id} с ролью {target_user['role']}")
            return jsonify({'error': 'Руководитель может управлять правами только менеджеров'}), 403
    
    perms = get_user_module_permissions(user_id)
    return jsonify(perms)


@admin_bp.route('/permissions/modules/<int:user_id>', methods=['POST'])
def update_user_module_perms(user_id):
    """Обновление прав пользователя на модули"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    # Нельзя менять свои собственные права через этот эндпоинт
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя изменять свои собственные права'}), 403
    
    if current_user.role == 'manager':
        target_user = get_user_by_id(user_id)
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        if target_user['role'] != 'viewer':
            return jsonify({'error': 'Руководитель может управлять правами только менеджеров'}), 403
    
    data = request.get_json()
    
    for module, can_view in data.items():
        if module in ['dashboard', 'selection']:
            set_user_module_permission(user_id, module, can_view)
    
    log_user_action(current_user.id, 'update_module_perms', f"Обновлены права модулей для пользователя {user_id}", request.remote_addr)
    return jsonify({'success': True})


@admin_bp.route('/permissions/objects/<int:user_id>', methods=['GET'])
def get_user_object_perms(user_id):
    """Получение прав пользователя на объекты"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    # Разрешаем пользователю просматривать свои собственные права
    if user_id == current_user.id:
        perms = get_user_object_permissions(user_id)
        return jsonify(perms)
    
    # Для manager: проверяем, что он запрашивает права только для viewer
    if current_user.role == 'manager':
        target_user = get_user_by_id(user_id)
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        if target_user['role'] != 'viewer':
            logger.warning(f"Manager {current_user.id} пытается получить права объектов пользователя {user_id} с ролью {target_user['role']}")
            return jsonify({'error': 'Руководитель может управлять правами только менеджеров'}), 403
    
    perms = get_user_object_permissions(user_id)
    
    # Если текущий пользователь manager, фильтруем объекты, которые он сам видит
    if current_user.role == 'manager':
        my_perms = get_user_object_permissions(current_user.id)
        visible_objects = [obj_id for obj_id, p in my_perms.items() if p.get('selection', False)]
        perms = {obj_id: p for obj_id, p in perms.items() if obj_id in visible_objects}
    
    return jsonify(perms)


@admin_bp.route('/permissions/objects/<int:user_id>', methods=['POST'])
def update_user_object_perms(user_id):
    """Обновление прав пользователя на объекты (только для подбора объектов)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    # Нельзя менять свои собственные права через этот эндпоинт
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя изменять свои собственные права'}), 403
    
    if current_user.role == 'manager':
        target_user = get_user_by_id(user_id)
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        if target_user['role'] != 'viewer':
            return jsonify({'error': 'Руководитель может управлять правами только менеджеров'}), 403
        
        # Получаем объекты, которые сам видит руководитель
        my_perms = get_user_object_permissions(current_user.id)
        visible_objects_for_me = [obj_id for obj_id, perms in my_perms.items() if perms.get('selection', False)]
    
    data = request.get_json()
    
    for obj_id_str, perms in data.items():
        obj_id = int(obj_id_str)
        
        # Для manager: проверяем, что он не выдаёт доступ к объекту, который сам не видит
        if current_user.role == 'manager':
            if obj_id not in visible_objects_for_me:
                logger.warning(f"Manager {current_user.id} пытается выдать права на объект {obj_id}, к которому не имеет доступа")
                continue  # Пропускаем этот объект
        
        # Для дашборда всегда даём True (не ограничиваем)
        set_user_object_permission(
            user_id, obj_id,
            True,  # dashboard всегда доступен
            perms.get('selection', False)
        )
    
    log_user_action(current_user.id, 'update_object_perms', f"Обновлены права на объекты для пользователя {user_id}", request.remote_addr)
    return jsonify({'success': True})