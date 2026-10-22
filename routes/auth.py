# routes/auth.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, current_user
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
import logging

from database import get_user_by_username, update_user, log_user_action, get_user_module_permissions, is_system_admin
from models import User
from config import SESSION_DURATION_HOURS

logger = logging.getLogger(__name__)

# Создаём blueprint для аутентификации
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/', methods=['POST'])
def auth():
    """Авторизация пользователя"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    client_ip = request.remote_addr
    logger.info(f"Попытка входа пользователя '{username}' с IP: {client_ip}")
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Введите имя пользователя и пароль'}), 401
    
    user_data = get_user_by_username(username)
    
    if user_data:
        user = User(user_data)
        if user.check_password(password):
            # Вход успешен
            login_user(user, remember=True, duration=timedelta(hours=SESSION_DURATION_HOURS))
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session.permanent = True
            
            # Обновляем время последнего входа
            update_user(user.id, {'last_login': datetime.now().isoformat()})
            
            # Логируем успешный вход
            log_user_action(user.id, 'login_success', f"Успешный вход с IP {client_ip}", client_ip)
            
            logger.info(f"✅ Успешный вход пользователя '{username}' ({user.get_role_display_name()})")
            
            # Получаем права пользователя на модули
            module_perms = get_user_module_permissions(user.id)
            
            # Если права не установлены, даём базовые права
            if not module_perms:
                from database import set_user_module_permission
                set_user_module_permission(user.id, 'dashboard', True)
                set_user_module_permission(user.id, 'selection', True)
                module_perms = {'dashboard': True, 'selection': True}
            
            module_perms['admin'] = user.can_view_admin()
            return jsonify({
                'success': True,
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'role': user.role,
                'role_display': user.get_role_display_name(),
                'is_system_admin': is_system_admin(user.id),
                'can_view_vip': user.can_view_vip(),
                'module_permissions': module_perms
            })
    
    # Неудачная попытка входа
    logger.warning(f"❌ Неудачная попытка входа пользователя '{username}' с IP: {client_ip}")
    log_user_action(None, 'login_failed', f"Неудачная попытка входа пользователя '{username}'", client_ip)
    
    return jsonify({'success': False, 'error': 'Неверное имя пользователя или пароль'}), 401


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Выход из системы"""
    if current_user.is_authenticated:
        log_user_action(current_user.id, 'logout', "Выход из системы", request.remote_addr)
        logger.info(f"Пользователь '{current_user.username}' вышел из системы")
        logout_user()
    session.clear()
    return jsonify({'success': True})


@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """Получение информации о текущем пользователе"""
    if current_user.is_authenticated:
        # Use the same decisions as server authorization, including admin roles.
        module_perms = {name: current_user.can_view_module(name)
                        for name in ('dashboard', 'selection', 'worker_status', 'reports')}
        
        module_perms['admin'] = current_user.can_view_admin()
        return jsonify({
            'id': current_user.id,
            'username': current_user.username,
            'full_name': current_user.full_name,
            'email': current_user.email,
            'role': current_user.role,
            'role_display': current_user.get_role_display_name(),
            'is_system_admin': is_system_admin(current_user.id),
            'can_view_vip': current_user.can_view_vip(),
            'module_permissions': module_perms,
            'is_active': current_user.is_active
        })
    return jsonify({'error': 'Not authenticated'}), 401


@auth_bp.route('/check', methods=['GET'])
def check_auth():
    """Проверка статуса аутентификации"""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'username': current_user.username,
            'role': current_user.role
        })
    return jsonify({'authenticated': False}), 401
