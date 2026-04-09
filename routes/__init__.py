# routes/__init__.py
# -*- coding: utf-8 -*-

# Импорт blueprint'ов
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.dashboard import dashboard_bp
from routes.selection import selection_bp
from routes.admin_pages import admin_pages_bp
from routes.objects_admin import objects_admin_bp
from routes.requirements_admin import requirements_admin_bp

# Список всех blueprint'ов для удобного импорта
__all__ = [
    'auth_bp',
    'admin_bp', 
    'dashboard_bp',
    'selection_bp',
    'admin_pages_bp',
    'objects_admin_bp',
    'requirements_admin_bp',
    'init_dashboard_apis',
    'init_selection_apis'
]

# Импортируем функции инициализации из модулей
from routes.dashboard import init_dashboard_apis
from routes.selection import init_selection_apis