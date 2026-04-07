# routes/admin_pages.py
# -*- coding: utf-8 -*-
from flask import Blueprint, render_template
from flask_login import login_required, current_user
import logging

logger = logging.getLogger(__name__)

# Создаём blueprint для страницы админки
admin_pages_bp = Blueprint('admin_pages', __name__)


@admin_pages_bp.route('/admin')
@login_required
def admin_panel():
    """Страница управления пользователями (отдельная админка)"""
    # Проверяем права доступа
    if current_user.role not in ['admin', 'manager']:
        return render_template('no_access.html'), 403
    
    return render_template('admin_panel.html')