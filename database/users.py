# database/users.py
# -*- coding: utf-8 -*-
import sqlite3
import logging
from datetime import datetime, timedelta

from database.db_core import DB_NAME

logger = logging.getLogger(__name__)


def is_system_admin(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE id = ? AND role = "admin"', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row is not None and user_id == 1
    except Exception as e:
        logger.error(f"Ошибка при проверке системного администратора: {e}")
        return False


def get_user_by_id(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, password_hash, full_name, email, role, is_active, created_at, last_login
            FROM users WHERE id = ?
        ''', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'username': row[1],
                'password_hash': row[2],
                'full_name': row[3],
                'email': row[4],
                'role': row[5],
                'is_active': bool(row[6]),
                'created_at': row[7],
                'last_login': row[8]
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя: {e}")
        return None


def get_user_by_username(username):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, password_hash, full_name, email, role, is_active, created_at, last_login
            FROM users WHERE username = ? AND is_active = 1
        ''', (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'username': row[1],
                'password_hash': row[2],
                'full_name': row[3],
                'email': row[4],
                'role': row[5],
                'is_active': bool(row[6]),
                'created_at': row[7],
                'last_login': row[8]
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении пользователя: {e}")
        return None


def get_all_users():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, full_name, email, role, is_active, created_at, last_login
            FROM users ORDER BY id
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        users = []
        for row in rows:
            users.append({
                'id': row[0],
                'username': row[1],
                'full_name': row[2],
                'email': row[3],
                'role': row[4],
                'is_active': bool(row[5]),
                'created_at': row[6],
                'last_login': row[7]
            })
        return users
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
        return []


def create_user(username, password_hash, full_name, email, role, created_by):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, password_hash, full_name, email, role, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, password_hash, full_name, email, role, created_by))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"✅ Создан пользователь {username} (role: {role})")
        return user_id
    except sqlite3.IntegrityError:
        logger.warning(f"Пользователь {username} уже существует")
        return None
    except Exception as e:
        logger.error(f"Ошибка при создании пользователя: {e}")
        return None


def update_user(user_id, data):
    try:
        from contextlib import closing
        with closing(sqlite3.connect(DB_NAME)) as conn, conn:
            cursor = conn.cursor()
            updates = []
            params = []
            for field in ('password_hash', 'full_name', 'email', 'role', 'last_login'):
                if field in data:
                    updates.append(f'{field} = ?')
                    params.append(data[field])
            if 'is_active' in data:
                updates.append('is_active = ?')
                params.append(1 if data['is_active'] else 0)
            if updates:
                cursor.execute(f'UPDATE users SET {", ".join(updates)} WHERE id = ?',
                               [*params, user_id])
            if 'payroll_access' in data:
                cursor.execute('INSERT INTO user_module_permissions(user_id,module_name,can_view) VALUES(?,?,?) ON CONFLICT(user_id,module_name) DO UPDATE SET can_view=excluded.can_view', (user_id, 'payroll', int(data['payroll_access'])))
            if 'vip_access' in data or ('role' in data and data['role'] != 'admin'):
                table_exists = cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_vip_access'"
                ).fetchone() is not None
                if not table_exists and data.get('vip_access'):
                    raise sqlite3.OperationalError('Право VIP ещё не подготовлено')
                if table_exists:
                    if data.get('vip_access') and data.get('role', 'admin') == 'admin':
                        role = cursor.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
                        if user_id == 1 or not role or role[0] != 'admin':
                            raise ValueError('VIP доступен только администраторам, кроме системного')
                        cursor.execute('INSERT OR IGNORE INTO user_vip_access(user_id) VALUES(?)', (user_id,))
                    else:
                        cursor.execute('DELETE FROM user_vip_access WHERE user_id=?', (user_id,))
        logger.info('Обновлен пользователь %s', user_id)
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя: {e}")
        return False


def delete_user(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_active = 0 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Деактивирован пользователь {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при деактивации пользователя: {e}")
        return False


def hard_delete_user(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_vip_access'").fetchone():
            cursor.execute('DELETE FROM user_vip_access WHERE user_id=?', (user_id,))
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Полностью удален пользователь {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {e}")
        return False


def get_user_module_permissions(user_id):
    try:
        from access_policy import get_effective
        policy = get_effective(user_id)
        if policy is not None:
            return policy[0]
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT module_name, can_view FROM user_module_permissions WHERE user_id = ?
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        permissions = {}
        for row in rows:
            permissions[row[0]] = bool(row[1])
        return permissions
    except Exception as e:
        logger.error(f"Ошибка при получении прав на модули: {e}")
        return {}


def set_user_module_permission(user_id, module_name, can_view):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_module_permissions (user_id, module_name, can_view)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, module_name) DO UPDATE SET
                can_view = excluded.can_view,
                created_at = CURRENT_TIMESTAMP
        ''', (user_id, module_name, 1 if can_view else 0))
        conn.commit()
        conn.close()
        logger.info(f"✅ Установлено право {module_name}={can_view} для пользователя {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при установке прав на модуль: {e}")
        return False


def get_user_object_permissions(user_id):
    try:
        from access_policy import get_effective
        policy = get_effective(user_id)
        if policy is not None:
            return policy[1]
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT object_id, can_view_dashboard, can_view_selection 
            FROM user_object_permissions WHERE user_id = ?
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        permissions = {}
        for row in rows:
            permissions[row[0]] = {
                'dashboard': bool(row[1]),
                'selection': bool(row[2])
            }
        return permissions
    except Exception as e:
        logger.error(f"Ошибка при получении прав на объекты: {e}")
        return {}


def set_user_object_permission(user_id, object_id, can_view_dashboard, can_view_selection):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_object_permissions (user_id, object_id, can_view_dashboard, can_view_selection)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, object_id) DO UPDATE SET
                can_view_dashboard = excluded.can_view_dashboard,
                can_view_selection = excluded.can_view_selection,
                created_at = CURRENT_TIMESTAMP
        ''', (user_id, object_id, 
              1 if can_view_dashboard else 0,
              1 if can_view_selection else 0))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при установке прав на объект: {e}")
        return False


def grant_all_objects_access(user_id, can_view_dashboard=True, can_view_selection=True):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM objects_settings')
        all_objects = cursor.fetchall()
        
        for obj in all_objects:
            cursor.execute('''
                INSERT INTO user_object_permissions (user_id, object_id, can_view_dashboard, can_view_selection)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, object_id) DO UPDATE SET
                    can_view_dashboard = excluded.can_view_dashboard,
                    can_view_selection = excluded.can_view_selection
            ''', (user_id, obj[0], 1 if can_view_dashboard else 0, 1 if can_view_selection else 0))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Пользователю {user_id} выданы права на все объекты")
        return True
    except Exception as e:
        logger.error(f"Ошибка при выдаче прав на объекты: {e}")
        return False


def log_user_action(user_id, action, details=None, ip_address=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_audit_log (user_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
        ''', (user_id, action, details, ip_address))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при логировании действия: {e}")
        return False


def update_user_profile(user_id, full_name=None, email=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if full_name is not None:
            updates.append('full_name = ?')
            params.append(full_name)
        if email is not None:
            updates.append('email = ?')
            params.append(email)
        
        if updates:
            params.append(user_id)
            cursor.execute(f'UPDATE users SET {", ".join(updates)} WHERE id = ?', params)
            conn.commit()
            logger.info(f"Обновлён профиль пользователя {user_id}")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля: {e}")
        return False


def change_user_password(user_id, new_password_hash):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_password_hash, user_id))
        conn.commit()
        conn.close()
        logger.info(f"Изменён пароль пользователя {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при изменении пароля: {e}")
        return False


def get_user_avatar(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT avatar_filename FROM user_avatars WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Ошибка при получении аватара: {e}")
        return None


def save_user_avatar(user_id, filename):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_avatars (user_id, avatar_filename, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                avatar_filename = excluded.avatar_filename,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, filename))
        conn.commit()
        conn.close()
        logger.info(f"Сохранён аватар для пользователя {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении аватара: {e}")
        return False


def delete_user_avatar(user_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_avatars WHERE user_id = ?', (user_id,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted:
            logger.info(f"Удалён аватар пользователя {user_id}")
        return deleted > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении аватара: {e}")
        return False


def cleanup_old_records(days=30):
    """Очищает старые записи вакансий (старше указанного количества дней)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        cursor.execute('DELETE FROM vacancy_requirements WHERE date < ?', (cutoff_date,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        logger.info(f"Очищено {deleted_count} старых записей вакансий (старше {days} дней)")
        return deleted_count
    except Exception as e:
        logger.error(f"Ошибка при очистке старых записей: {e}")
        return 0


def cleanup_old_unused_avatars():
    try:
        import os
        from flask import current_app
        
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
        if not os.path.exists(upload_dir):
            return 0
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT avatar_filename FROM user_avatars')
        used_avatars = set(row[0] for row in cursor.fetchall())
        conn.close()
        
        deleted_count = 0
        for filename in os.listdir(upload_dir):
            if filename not in used_avatars:
                file_path = os.path.join(upload_dir, filename)
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception:
                    pass
        
        if deleted_count > 0:
            logger.info(f"Очищено {deleted_count} неиспользуемых аватаров")
        
        return deleted_count
    except Exception as e:
        logger.error(f"Ошибка очистки аватаров: {e}")
        return 0
