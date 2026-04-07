# routes/__init__.py
# -*- coding: utf-8 -*-
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.dashboard import dashboard_bp, init_dashboard_apis, clear_cache
from routes.selection import selection_bp, init_selection_apis
from routes.admin_pages import admin_pages_bp

__all__ = [
    'auth_bp',
    'admin_bp', 
    'dashboard_bp',
    'selection_bp',
    'admin_pages_bp',
    'init_dashboard_apis',
    'init_selection_apis',
    'clear_cache'
]