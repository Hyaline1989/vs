# permissions.py
# -*- coding: utf-8 -*-
from functools import wraps
from flask import jsonify, request, g
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)

# ========== ДЕКОРАТОРЫ ДЛЯ ПРОВЕРКИ ПРАВ ==========

def login_required_api(f):
    """
    Декоратор для API эндпоинтов - проверяет авторизацию пользователя
    Возвращает JSON ошибку вместо редиректа
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized', 'message': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_role(role):
    """
    Декоратор для проверки роли пользователя
    
    Args:
        role: 'admin', 'manager' или 'viewer'
    
    Использование:
        @require_role('admin')
        def admin_only_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Unauthorized', 'message': 'Требуется авторизация'}), 401
            
            if current_user.role != role and current_user.role != 'admin':
                return jsonify({
                    'error': 'Forbidden', 
                    'message': f'Доступ только для {role}'
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_any_role(*roles):
    """
    Декоратор для проверки, что пользователь имеет одну из указанных ролей
    
    Args:
        *roles: список допустимых ролей ('admin', 'manager', 'viewer')
    
    Использование:
        @require_any_role('admin', 'manager')
        def manager_or_admin_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Unauthorized', 'message': 'Требуется авторизация'}), 401
            
            if current_user.role not in roles and current_user.role != 'admin':
                return jsonify({
                    'error': 'Forbidden', 
                    'message': f'Доступ только для: {", ".join(roles)}'
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_module(module_name):
    """
    Декоратор для проверки доступа к модулю (дашборд или подбор объектов)
    
    Args:
        module_name: 'dashboard' или 'selection'
    
    Использование:
        @require_module('dashboard')
        def dashboard_endpoint():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Unauthorized', 'message': 'Требуется авторизация'}), 401
            
            if not current_user.can_view_module(module_name):
                module_names = {
                    'dashboard': 'Дашборд',
                    'selection': 'Подбор объектов'
                }
                module_display = module_names.get(module_name, module_name)
                return jsonify({
                    'error': 'Forbidden',
                    'message': f'У вас нет доступа к модулю "{module_display}"'
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_object_permission(object_id_param='object_id', context='selection'):
    """
    Декоратор для проверки доступа к конкретному объекту
    
    Args:
        object_id_param: имя параметра в URL, содержащего ID объекта
        context: 'dashboard' или 'selection' - контекст проверки
    
    Использование:
        @require_object_permission('object_id', 'selection')
        def object_endpoint(object_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Unauthorized', 'message': 'Требуется авторизация'}), 401
            
            # Получаем ID объекта из аргументов
            object_id = kwargs.get(object_id_param)
            
            # Если ID не передан, проверяем, есть ли он в request
            if object_id is None:
                # Проверяем в JSON теле
                if request.is_json:
                    object_id = request.json.get(object_id_param)
                # Проверяем в query параметрах
                if object_id is None:
                    object_id = request.args.get(object_id_param)
                # Проверяем в form data
                if object_id is None:
                    object_id = request.form.get(object_id_param)
            
            if object_id is None:
                # Если ID не найден, пропускаем проверку (будет проверка в самом эндпоинте)
                logger.warning(f"Object ID not found in request for {f.__name__}")
                return f(*args, **kwargs)
            
            # Преобразуем в int
            try:
                object_id = int(object_id)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid object ID'}), 400
            
            # Проверяем доступ
            if not current_user.can_view_object(object_id, context):
                return jsonify({
                    'error': 'Forbidden',
                    'message': f'У вас нет доступа к этому объекту'
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_objects_permission(objects_param='object_ids', context='selection'):
    """
    Декоратор для проверки доступа к нескольким объектам
    
    Args:
        objects_param: имя параметра, содержащего список ID объектов
        context: 'dashboard' или 'selection'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Unauthorized', 'message': 'Требуется авторизация'}), 401
            
            # Получаем список ID объектов
            object_ids = kwargs.get(objects_param)
            
            if object_ids is None and request.is_json:
                object_ids = request.json.get(objects_param)
            
            if object_ids is None:
                return f(*args, **kwargs)
            
            # Преобразуем в список
            if isinstance(object_ids, (int, str)):
                object_ids = [int(object_ids)] if str(object_ids).isdigit() else []
            elif isinstance(object_ids, list):
                object_ids = [int(obj_id) for obj_id in object_ids if str(obj_id).isdigit()]
            
            # Проверяем каждый объект
            for obj_id in object_ids:
                if not current_user.can_view_object(obj_id, context):
                    return jsonify({
                        'error': 'Forbidden',
                        'message': f'У вас нет доступа к объекту с ID {obj_id}'
                    }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_permission_to_manage_user(target_user_id_param='user_id'):
    """
    Декоратор для проверки, может ли пользователь управлять другим пользователем
    
    Правила:
    - Администратор может управлять любым пользователем
    - Руководитель может управлять только менеджерами (viewer)
    - Менеджер не может управлять другими
    
    Args:
        target_user_id_param: имя параметра с ID целевого пользователя
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Unauthorized', 'message': 'Требуется авторизация'}), 401
            
            # Получаем ID целевого пользователя
            target_user_id = kwargs.get(target_user_id_param)
            
            if target_user_id is None and request.is_json:
                target_user_id = request.json.get(target_user_id_param)
            
            if target_user_id is None:
                target_user_id = request.args.get(target_user_id_param)
            
            if target_user_id is None:
                return jsonify({'error': 'User ID not provided'}), 400
            
            try:
                target_user_id = int(target_user_id)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid user ID'}), 400
            
            # Администратор может всё
            if current_user.is_admin():
                return f(*args, **kwargs)
            
            # Проверяем, не пытается ли пользователь управлять собой
            if target_user_id == current_user.id:
                return jsonify({
                    'error': 'Forbidden',
                    'message': 'Вы не можете управлять своей учётной записью через этот интерфейс'
                }), 403
            
            # Получаем данные целевого пользователя
            from database import get_user_by_id
            target_user = get_user_by_id(target_user_id)
            
            if not target_user:
                return jsonify({'error': 'User not found'}), 404
            
            # Руководитель может управлять только менеджерами (viewer)
            if current_user.is_manager() and target_user['role'] == 'viewer':
                return f(*args, **kwargs)
            
            return jsonify({
                'error': 'Forbidden',
                'message': 'У вас недостаточно прав для управления этим пользователем'
            }), 403
        
        return decorated_function
    return decorator


def log_action(action):
    """
    Декоратор для логирования действий пользователя
    
    Args:
        action: название действия (например, 'update_user', 'delete_object')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return f(*args, **kwargs)
            
            # Запоминаем время начала
            import time
            start_time = time.time()
            
            # Выполняем функцию
            response = f(*args, **kwargs)
            
            # Логируем действие
            try:
                from database import log_user_action
                
                # Собираем детали
                details = {
                    'endpoint': request.endpoint,
                    'method': request.method,
                    'url': request.url,
                    'args': dict(request.args),
                    'duration_ms': round((time.time() - start_time) * 1000, 2)
                }
                
                # Добавляем JSON тело если есть
                if request.is_json:
                    details['json'] = request.get_json()
                
                # Добавляем результат если это JSON
                if response and hasattr(response, 'get_json'):
                    response_data = response.get_json()
                    if response_data and 'error' not in response_data:
                        details['success'] = True
                    elif response_data and 'error' in response_data:
                        details['error'] = response_data.get('error')
                
                log_user_action(
                    user_id=current_user.id,
                    action=action,
                    details=str(details),
                    ip_address=request.remote_addr
                )
            except Exception as e:
                logger.error(f"Ошибка при логировании действия {action}: {e}")
            
            return response
        return decorated_function
    return decorator


# ========== КОНТЕКСТНЫЕ ПРОЦЕССОРЫ ДЛЯ ШАБЛОНОВ ==========

def inject_user_permissions():
    """
    Контекстный процессор для передачи прав пользователя в шаблоны
    Использовать в app.py:
        app.context_processor(inject_user_permissions)
    """
    if current_user.is_authenticated:
        return {
            'current_user': current_user,
            'can_view_dashboard': current_user.can_view_dashboard(),
            'can_view_selection': current_user.can_view_selection(),
            'is_admin': current_user.is_admin(),
            'is_manager': current_user.is_manager(),
            'user_role_display': current_user.get_role_display_name()
        }
    return {
        'current_user': None,
        'can_view_dashboard': False,
        'can_view_selection': False,
        'is_admin': False,
        'is_manager': False,
        'user_role_display': None
    }


# ========== УТИЛИТЫ ДЛЯ ФИЛЬТРАЦИИ ДАННЫХ ==========

def filter_objects_by_permission(objects_list, context='selection'):
    """
    Фильтрует список объектов по правам пользователя
    
    Args:
        objects_list: список объектов (каждый объект должен иметь поле 'id')
        context: 'dashboard' или 'selection'
    
    Returns:
        list: отфильтрованный список объектов
    """
    if not current_user.is_authenticated:
        return []
    
    if current_user.is_admin():
        return objects_list
    
    visible_ids = current_user.get_visible_objects(context)
    return [obj for obj in objects_list if obj.get('id') in visible_ids]


def filter_objects_data_by_permission(objects_data, context='selection'):
    """
    Фильтрует словарь с данными объектов по правам пользователя
    
    Args:
        objects_data: словарь вида {object_id: data}
        context: 'dashboard' или 'selection'
    
    Returns:
        dict: отфильтрованный словарь
    """
    if not current_user.is_authenticated:
        return {}
    
    if current_user.is_admin():
        return objects_data
    
    visible_ids = current_user.get_visible_objects(context)
    return {obj_id: data for obj_id, data in objects_data.items() if obj_id in visible_ids}


def can_user_access_object(object_id, context='selection'):
    """
    Проверяет доступ пользователя к объекту
    
    Returns:
        bool
    """
    if not current_user.is_authenticated:
        return False
    
    return current_user.can_view_object(object_id, context)


# ========== КЛАСС ДЛЯ УПРАВЛЕНИЯ ПРАВАМИ В ШАБЛОНАХ ==========

class PermissionChecker:
    """
    Класс для удобной проверки прав в шаблонах Jinja2
    Использовать в шаблонах:
        {% if permissions.can_edit_user(user) %}
            <button>Редактировать</button>
        {% endif %}
    """
    def __init__(self, current_user):
        self.user = current_user
    
    def can_view_dashboard(self):
        return self.user.is_authenticated and self.user.can_view_dashboard()
    
    def can_view_selection(self):
        return self.user.is_authenticated and self.user.can_view_selection()
    
    def can_manage_users(self):
        return self.user.is_authenticated and self.user.can_manage_users()
    
    def can_create_users(self):
        return self.user.is_authenticated and self.user.can_create_users()
    
    def can_delete_users(self):
        return self.user.is_authenticated and self.user.can_delete_users()
    
    def can_edit_user(self, target_user):
        """Проверяет, может ли текущий пользователь редактировать target_user"""
        if not self.user.is_authenticated:
            return False
        
        if self.user.is_admin():
            return True
        
        if self.user.is_manager() and target_user and target_user.get('role') == 'viewer':
            return True
        
        return False
    
    def can_delete_user(self, target_user):
        """Проверяет, может ли текущий пользователь удалять target_user"""
        if not self.user.is_authenticated:
            return False
        
        if self.user.is_admin() and target_user and target_user.get('id') != self.user.id:
            return True
        
        return False
    
    def can_view_object(self, object_id, context='selection'):
        return self.user.is_authenticated and self.user.can_view_object(object_id, context)
    
    def get_visible_objects(self, context='selection'):
        if not self.user.is_authenticated:
            return []
        return self.user.get_visible_objects(context)


def inject_permission_checker():
    """
    Контекстный процессор для добавления PermissionChecker в шаблоны
    """
    if current_user.is_authenticated:
        return {'permissions': PermissionChecker(current_user)}
    return {'permissions': None}