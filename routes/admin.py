# routes/admin.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session
from flask_login import current_user, login_user
from werkzeug.security import generate_password_hash
import logging
import sqlite3

from database import (
    get_all_users, get_user_by_id, create_user, update_user, hard_delete_user,
    get_user_module_permissions, get_user_object_permissions,
    set_user_module_permission, set_user_object_permission, grant_all_objects_access,
    log_user_action, DB_NAME, is_system_admin
)
from models import User

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
    set_user_module_permission(user_id, 'worker_status', True)
    set_user_module_permission(user_id, 'reports', False)
    
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
    
    if user_id == current_user.id:
        perms = get_user_module_permissions(user_id)
        return jsonify(perms)
    
    if current_user.role == 'manager':
        target_user = get_user_by_id(user_id)
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        if target_user['role'] != 'viewer':
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
    
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя изменять свои собственные права'}), 403
    
    if current_user.role == 'manager':
        target_user = get_user_by_id(user_id)
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        if target_user['role'] != 'viewer':
            return jsonify({'error': 'Руководитель может управлять правами только менеджеров'}), 403
        my_module_perms = get_user_module_permissions(current_user.id)
    
    data = request.get_json()
    logger.info(f"DEBUG: Получены права на модули для user {user_id}: {data}")
    
    # Убеждаемся, что таблица имеет правильный CHECK constraint
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(user_module_permissions)")
        columns = cursor.fetchall()
        
        # Проверяем constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_module_permissions'")
        create_sql = cursor.fetchone()
        if create_sql and "reports" not in create_sql[0]:
            logger.warning("Таблица user_module_permissions не имеет reports в CHECK, обновляем...")
            # Пересоздаём таблицу с правильным CHECK
            cursor.execute("CREATE TABLE user_module_permissions_new (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT," +
                "user_id INTEGER NOT NULL," +
                "module_name TEXT NOT NULL CHECK(module_name IN ('dashboard', 'selection', 'worker_status', 'reports'))," +
                "can_view INTEGER DEFAULT 0," +
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP," +
                "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE," +
                "UNIQUE(user_id, module_name))")
            cursor.execute("INSERT INTO user_module_permissions_new (id, user_id, module_name, can_view, created_at) " +
                         "SELECT id, user_id, module_name, can_view, created_at FROM user_module_permissions")
            cursor.execute("DROP TABLE user_module_permissions")
            cursor.execute("ALTER TABLE user_module_permissions_new RENAME TO user_module_permissions")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_module_perms_user ON user_module_permissions (user_id)")
            conn.commit()
            logger.info("✅ Таблица user_module_permissions обновлена")
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка при проверке структуры таблицы: {e}")
    
    for module, can_view in data.items():
        if module in ['dashboard', 'selection', 'worker_status', 'reports']:
            if current_user.role == 'manager':
                if not my_module_perms.get(module, False):
                    logger.warning(f"Manager {current_user.id} пытается выдать доступ к модулю {module}")
                    continue
            result = set_user_module_permission(user_id, module, can_view)
            logger.info(f"DEBUG: Установлено право {module}={can_view} для user {user_id}, результат={result}")
    
    log_user_action(current_user.id, 'update_module_perms', f"Обновлены права модулей для пользователя {user_id}", request.remote_addr)
    return jsonify({'success': True})


@admin_bp.route('/permissions/objects/<int:user_id>', methods=['GET'])
def get_user_object_perms(user_id):
    """Получение прав пользователя на объекты"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    if user_id == current_user.id:
        perms = get_user_object_permissions(user_id)
        return jsonify(perms)
    
    if current_user.role == 'manager':
        target_user = get_user_by_id(user_id)
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        if target_user['role'] != 'viewer':
            return jsonify({'error': 'Руководитель может управлять правами только менеджеров'}), 403
    
    perms = get_user_object_permissions(user_id)
    
    if current_user.role == 'manager':
        my_perms = get_user_object_permissions(current_user.id)
        visible_objects = [obj_id for obj_id, p in my_perms.items() if p.get('selection', False)]
        perms = {obj_id: p for obj_id, p in perms.items() if obj_id in visible_objects}
    
    return jsonify(perms)


@admin_bp.route('/permissions/objects/<int:user_id>', methods=['POST'])
def update_user_object_perms(user_id):
    """Обновление прав пользователя на объекты"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin', 'manager']:
        return jsonify({'error': 'Forbidden'}), 403
    
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя изменять свои собственные права'}), 403
    
    if current_user.role == 'manager':
        target_user = get_user_by_id(user_id)
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        if target_user['role'] != 'viewer':
            return jsonify({'error': 'Руководитель может управлять правами только менеджеров'}), 403
        my_perms = get_user_object_permissions(current_user.id)
        visible_objects_for_me = [obj_id for obj_id, perms in my_perms.items() if perms.get('selection', False)]
    
    data = request.get_json()
    logger.info(f"DEBUG: Получены права на объекты для user {user_id}: {data}")
    
    for obj_id_str, perms in data.items():
        obj_id = int(obj_id_str)
        
        if current_user.role == 'manager':
            if obj_id not in visible_objects_for_me:
                logger.warning(f"Manager {current_user.id} пытается выдать права на объект {obj_id}")
                continue
        
        set_user_object_permission(user_id, obj_id, True, perms.get('selection', False))
    
    log_user_action(current_user.id, 'update_object_perms', f"Обновлены права на объекты для пользователя {user_id}", request.remote_addr)
    return jsonify({'success': True})


# ========== ДИАГНОСТИЧЕСКИЙ ЭНДПОИНТ ==========

@admin_bp.route('/debug/db-check', methods=['GET'])
def debug_db_check():
    """Проверка структуры БД"""
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(user_module_permissions)")
    columns = cursor.fetchall()
    
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_module_permissions'")
    create_sql = cursor.fetchone()
    
    cursor.execute("SELECT DISTINCT module_name FROM user_module_permissions")
    existing_modules = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'columns': columns,
        'create_sql': create_sql[0] if create_sql else None,
        'existing_modules': existing_modules,
        'expected_modules': ['dashboard', 'selection', 'worker_status', 'reports']
    })


# ========== ИМПЕРСОНАЦИЯ (ВХОД КАК ПОЛЬЗОВАТЕЛЬ) ==========

@admin_bp.route('/impersonate/status', methods=['GET'])
def impersonation_status():
    """Проверка статуса имперсонации"""
    if not current_user.is_authenticated:
        return jsonify({'is_impersonating': False}), 401
    
    is_impersonating = session.get('is_impersonating', False)
    original_user_id = session.get('original_user_id')
    
    return jsonify({
        'is_impersonating': is_impersonating,
        'original_user_id': original_user_id
    })


@admin_bp.route('/impersonate/<int:user_id>', methods=['POST'])
def impersonate_user(user_id):
    """
    Вход под другим пользователем (только для системного администратора)
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Только системный администратор (id=1)
    if not is_system_admin(current_user.id):
        return jsonify({'error': 'Только системный администратор может входить как другой пользователь'}), 403
    
    # Нельзя войти как сам себя
    if user_id == current_user.id:
        return jsonify({'error': 'Вы уже вошли как этот пользователь'}), 400
    
    # Получаем данные пользователя
    target_user_data = get_user_by_id(user_id)
    if not target_user_data:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    if not target_user_data.get('is_active', True):
        return jsonify({'error': 'Пользователь заблокирован'}), 400
    
    from datetime import datetime
    
    # Сохраняем ID оригинального пользователя в сессии
    session['original_user_id'] = current_user.id
    session['is_impersonating'] = True
    
    # Создаём объект пользователя и выполняем вход
    target_user = User(target_user_data)
    login_user(target_user, remember=True)
    
    # Обновляем время последнего входа
    from database import update_user
    update_user(user_id, {'last_login': datetime.now().isoformat()})
    
    # Логируем действие
    log_user_action(
        current_user.id, 
        'impersonate', 
        f"Системный администратор вошёл как пользователь {target_user_data['username']} (ID: {user_id})",
        request.remote_addr
    )
    
    return jsonify({
        'success': True,
        'message': f'Вы вошли как {target_user_data["username"]}',
        'username': target_user_data['username']
    })


@admin_bp.route('/impersonate/stop', methods=['POST'])
def stop_impersonation():
    """
    Возврат к своему аккаунту (выход из имперсонации)
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем, что мы в режиме имперсонации
    if not session.get('is_impersonating', False):
        return jsonify({'error': 'Вы не в режиме имперсонации'}), 400
    
    original_user_id = session.get('original_user_id')
    if not original_user_id:
        return jsonify({'error': 'Оригинальный пользователь не найден'}), 400
    
    # Получаем данные оригинального пользователя
    original_user_data = get_user_by_id(original_user_id)
    if not original_user_data:
        return jsonify({'error': 'Оригинальный пользователь не найден'}), 404
    
    # Выходим из имперсонации
    session.pop('is_impersonating', None)
    session.pop('original_user_id', None)
    
    # Возвращаемся к оригинальному пользователю
    original_user = User(original_user_data)
    login_user(original_user, remember=True)
    
    # Логируем действие
    log_user_action(
        original_user_id, 
        'stop_impersonation', 
        f"Системный администратор вернулся к своему аккаунту",
        request.remote_addr
    )
    
    return jsonify({
        'success': True,
        'message': f'Вы вернулись к своему аккаунту ({original_user_data["username"]})'
    })
