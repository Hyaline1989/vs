# models.py
# -*- coding: utf-8 -*-
from flask_login import UserMixin
from werkzeug.security import check_password_hash
import logging
import sqlite3

logger = logging.getLogger(__name__)

class User(UserMixin):
    """
    Модель пользователя для Flask-Login
    """
    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.password_hash = user_data['password_hash']
        self.full_name = user_data.get('full_name', '')
        self.email = user_data.get('email', '')
        self.role = user_data.get('role', 'viewer')
        self._is_active = user_data.get('is_active', True)
        self.created_at = user_data.get('created_at')
        self.last_login = user_data.get('last_login')
        
        # Кэш для прав доступа
        self._module_permissions = None
        self._object_permissions = None
        
        logger.debug(f"User {self.username} created with role {self.role}")
    
    @property
    def is_active(self):
        """Возвращает статус активности пользователя (требуется Flask-Login)"""
        return self._is_active
    
    @is_active.setter
    def is_active(self, value):
        """Устанавливает статус активности пользователя"""
        self._is_active = value
    
    def check_password(self, password):
        if not password or not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_manager(self):
        return self.role == 'manager'
    
    def is_viewer(self):
        return self.role == 'viewer'
    
    def is_system_admin(self):
        """Проверяет, является ли пользователь системным администратором (ID=1)"""
        from database import is_system_admin
        return is_system_admin(self.id)
    
    def can_manage_users(self):
        """Может ли пользователь управлять другими пользователями"""
        return self.role in ['admin', 'manager']
    
    def can_create_users(self):
        """Может ли пользователь создавать новых пользователей"""
        return self.role == 'admin'
    
    def can_delete_users(self):
        """Может ли пользователь удалять пользователей"""
        return self.role == 'admin'
    
    def _ensure_required_permissions(self):
        """Проверяет и создаёт недостающие записи прав для пользователя"""
        required_modules = ['dashboard', 'selection', 'worker_status', 'reports']
        
        for module in required_modules:
            if module not in self._module_permissions:
                try:
                    from database import set_user_module_permission
                    logger.info(f"Автоматически создаю права для модуля '{module}' пользователю {self.id} ({self.username})")
                    set_user_module_permission(self.id, module, False)
                    self._module_permissions[module] = False
                except Exception as e:
                    logger.error(f"Ошибка при создании прав для модуля '{module}': {e}")
    
    def _load_permissions(self):
        """Загружает права доступа из базы данных"""
        if self._module_permissions is None or self._object_permissions is None:
            try:
                from access_policy import get_effective
                policy = get_effective(self.id)
                if policy is not None:
                    self._module_permissions, self._object_permissions = policy
                    return
                from database import DB_NAME
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                
                # Загружаем права на модули
                cursor.execute('''
                    SELECT module_name, can_view 
                    FROM user_module_permissions 
                    WHERE user_id = ?
                ''', (self.id,))
                rows = cursor.fetchall()
                
                self._module_permissions = {}
                for row in rows:
                    self._module_permissions[row[0]] = bool(row[1])
                
                # Загружаем права на объекты
                cursor.execute('''
                    SELECT object_id, can_view_dashboard, can_view_selection 
                    FROM user_object_permissions 
                    WHERE user_id = ?
                ''', (self.id,))
                self._object_permissions = {
                    row[0]: {
                        'dashboard': bool(row[1]),
                        'selection': bool(row[2])
                    } for row in cursor.fetchall()
                }
                
                conn.close()
                
                # АВТОМАТИЧЕСКИ СОЗДАЁМ НЕДОСТАЮЩИЕ ЗАПИСИ ПРАВ
                self._ensure_required_permissions()
                
                logger.debug(f"Loaded permissions for {self.username}: modules={self._module_permissions}")
                
            except Exception as e:
                logger.error(f"Ошибка загрузки прав для {self.username}: {e}")
                self._module_permissions = {}
                self._object_permissions = {}
    
    def can_view_module(self, module_name):
        """Проверяет доступ к модулю (dashboard, selection, worker_status)"""
        try:
            if self.is_admin():
                return True
            if self._module_permissions is None:
                self._load_permissions()
            return self._module_permissions.get(module_name, False)
        except Exception as e:
            logger.error(f"Ошибка проверки прав на модуль {module_name}: {e}")
            return False
    
    def can_view_dashboard(self):
        """Проверяет доступ к дашборду"""
        return self.can_view_module('dashboard')
    
    def can_view_selection(self):
        """Проверяет доступ к подбору объектов"""
        return self.can_view_module('selection')
    
    def can_view_worker_status(self):
        """Проверяет доступ к модулю Вахтовики"""
        return self.can_view_module('worker_status')

    def can_view_reports(self):
        """Проверяет доступ к разделу отчётов."""
        return self.can_view_module('reports')

    def can_view_admin(self):
        if self.is_admin():
            return True
        from access_policy import get_effective
        policy = get_effective(self.id)
        return policy[0]['admin'] if policy is not None else self.role == 'manager'
    
    def can_view_object(self, object_id, context='selection'):
        """Проверяет доступ к конкретному объекту"""
        try:
            if self.is_admin():
                return True
            if context == 'dashboard' and not self.can_view_dashboard():
                return False
            if context == 'selection' and not self.can_view_selection():
                return False
            if self._object_permissions is None:
                self._load_permissions()
            object_perms = self._object_permissions.get(object_id, {})
            if context == 'dashboard':
                return object_perms.get('dashboard', False)
            else:
                return object_perms.get('selection', False)
        except Exception as e:
            logger.error(f"Ошибка проверки прав на объект {object_id}: {e}")
            return False
    
    def get_visible_objects(self, context='selection'):
        """Возвращает список ID объектов, доступных пользователю"""
        try:
            if self.is_admin():
                from config import OBJECTS_BASE
                return [obj['id'] for obj in OBJECTS_BASE]
            if self._object_permissions is None:
                self._load_permissions()
            visible_objects = []
            for obj_id, perms in self._object_permissions.items():
                if context == 'dashboard' and perms.get('dashboard', False):
                    visible_objects.append(obj_id)
                elif context == 'selection' and perms.get('selection', False):
                    visible_objects.append(obj_id)
            return visible_objects
        except Exception as e:
            logger.error(f"Ошибка получения видимых объектов: {e}")
            return []
    
    def get_role_display_name(self):
        """Возвращает отображаемое название роли"""
        if self.is_system_admin():
            return 'Системный администратор'
        role_names = {
            'admin': 'Администратор',
            'manager': 'Руководитель',
            'viewer': 'Менеджер'
        }
        return role_names.get(self.role, 'Пользователь')
    
    def to_dict(self):
        """Преобразует пользователя в словарь для JSON"""
        return {
            'id': self.id,
            'username': self.username,
            'full_name': self.full_name,
            'email': self.email,
            'role': self.role,
            'role_display': self.get_role_display_name(),
            'is_system_admin': self.is_system_admin(),
            'is_active': self._is_active,
            'created_at': self.created_at,
            'last_login': self.last_login
        }
    
    def __repr__(self):
        return f'<User {self.username} ({self.get_role_display_name()})>'
