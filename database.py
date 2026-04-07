# database.py
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timedelta
import logging
import json
import re

logger = logging.getLogger(__name__)

DB_NAME = 'requirements.db'

# ========== ФУНКЦИЯ САНИТАРИИ НАЗВАНИЙ ==========
def sanitize_object_name(name):
    """Очищает название объекта от опасных символов"""
    if not name:
        return name
    return re.sub(r'[^\w\s\u0400-\u04FF.-]', '', name)

def init_db():
    """Создает таблицы, если их нет"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Таблица для хранения максимальных потребностей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requirement_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_name TEXT NOT NULL,
                date TEXT NOT NULL,
                max_count INTEGER NOT NULL,
                is_high INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(object_name, date)
            )
        ''')
        
        cursor.execute("PRAGMA table_info(requirement_history)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'is_high' not in columns:
            cursor.execute("ALTER TABLE requirement_history ADD COLUMN is_high INTEGER DEFAULT 0")
        
        # Таблица для настроек объектов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objects_settings (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                visible INTEGER DEFAULT 1,
                priority INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица для глобального порядка объектов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_objects_order (
                id INTEGER PRIMARY KEY DEFAULT 1,
                object_order TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                email TEXT,
                role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'viewer')),
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                last_login TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        ''')
        
        # Таблица прав доступа к модулям
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_module_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                module_name TEXT NOT NULL CHECK(module_name IN ('dashboard', 'selection')),
                can_view INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, module_name)
            )
        ''')
        
        # Таблица прав доступа к объектам
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_object_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                object_id INTEGER NOT NULL,
                can_view_dashboard INTEGER DEFAULT 0,
                can_view_selection INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (object_id) REFERENCES objects_settings(id) ON DELETE CASCADE,
                UNIQUE(user_id, object_id)
            )
        ''')
        
        # Таблица для аудита
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        
        # Индексы
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON requirement_history (date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_objects_visible ON objects_settings (visible)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_objects_priority ON objects_settings (priority)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users (role)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_module_perms_user ON user_module_permissions (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_object_perms_user ON user_object_permissions (user_id)')
        
        conn.commit()
        
        # Создаем системного администратора по умолчанию, если нет пользователей
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            logger.info("Создаю системного администратора...")
            from werkzeug.security import generate_password_hash
            
            default_password = generate_password_hash('admin123')
            
            cursor.execute('''
                INSERT INTO users (id, username, password_hash, full_name, role, created_by)
                VALUES (1, ?, ?, ?, ?, ?)
            ''', ('admin', default_password, 'Системный администратор', 'admin', 1))
            
            admin_id = 1
            
            # Даем полный доступ ко всем модулям
            cursor.execute('''
                INSERT INTO user_module_permissions (user_id, module_name, can_view)
                VALUES (?, 'dashboard', 1), (?, 'selection', 1)
            ''', (admin_id, admin_id))
            
            # Даем доступ ко всем объектам
            cursor.execute('SELECT id FROM objects_settings')
            all_objects = cursor.fetchall()
            for obj in all_objects:
                cursor.execute('''
                    INSERT INTO user_object_permissions (user_id, object_id, can_view_dashboard, can_view_selection)
                    VALUES (?, ?, 1, 1)
                ''', (admin_id, obj[0]))
            
            conn.commit()
            logger.info("✅ Системный администратор создан (ID=1, логин: admin, пароль: admin123)")
            logger.warning("⚠️ ВАЖНО: Смените пароль системного администратора при первом входе!")
        
        conn.close()
        logger.info(f"База данных {DB_NAME} инициализирована")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}")
        return False

# ========== ФУНКЦИИ ДЛЯ ПРОВЕРКИ СИСТЕМНОГО АДМИНА ==========

def is_system_admin(user_id):
    """Проверяет, является ли пользователь системным администратором (ID=1)"""
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

# ========== ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ ==========

def get_user_by_id(user_id):
    """Получает пользователя по ID"""
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
    """Получает пользователя по имени пользователя"""
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

def create_user(username, password_hash, full_name, email, role, created_by):
    """Создает нового пользователя"""
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
    """Обновляет данные пользователя"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if 'password_hash' in data:
            updates.append('password_hash = ?')
            params.append(data['password_hash'])
        if 'full_name' in data:
            updates.append('full_name = ?')
            params.append(data['full_name'])
        if 'email' in data:
            updates.append('email = ?')
            params.append(data['email'])
        if 'role' in data:
            updates.append('role = ?')
            params.append(data['role'])
        if 'is_active' in data:
            updates.append('is_active = ?')
            params.append(1 if data['is_active'] else 0)
        if 'last_login' in data:
            updates.append('last_login = ?')
            params.append(data['last_login'])
        
        if updates:
            params.append(user_id)
            cursor.execute(f'UPDATE users SET {", ".join(updates)} WHERE id = ?', params)
            conn.commit()
            logger.info(f"Обновлен пользователь {user_id}")
        
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении пользователя: {e}")
        return False

def delete_user(user_id):
    """Деактивирует пользователя"""
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
    """Полностью удаляет пользователя из БД"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Полностью удален пользователь {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {e}")
        return False

def get_all_users():
    """Получает список всех пользователей"""
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

# ========== ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ПРАВАМИ ==========

def get_user_module_permissions(user_id):
    """Получает права пользователя на модули"""
    try:
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
    """Устанавливает право на модуль для пользователя"""
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
        return True
    except Exception as e:
        logger.error(f"Ошибка при установке прав на модуль: {e}")
        return False

def get_user_object_permissions(user_id):
    """Получает права пользователя на объекты"""
    try:
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
    """Устанавливает право на объект для пользователя"""
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
    """Дает доступ ко всем объектам"""
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

# ========== ФУНКЦИИ ДЛЯ АУДИТА ==========

def log_user_action(user_id, action, details=None, ip_address=None):
    """Логирует действие пользователя"""
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

def get_user_audit_log(user_id=None, limit=100):
    """Получает лог действий пользователя"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT id, user_id, action, details, ip_address, created_at
                FROM user_audit_log
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
        else:
            cursor.execute('''
                SELECT id, user_id, action, details, ip_address, created_at
                FROM user_audit_log
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        logs = []
        for row in rows:
            logs.append({
                'id': row[0],
                'user_id': row[1],
                'action': row[2],
                'details': row[3],
                'ip_address': row[4],
                'created_at': row[5]
            })
        return logs
    except Exception as e:
        logger.error(f"Ошибка при получении лога: {e}")
        return []

# ========== ФУНКЦИИ ДЛЯ ПРОЕКТА 1 (Потребности) ==========

def update_max_requirement(object_name, count, is_high=False, target_date=None):
    """Обновляет МАКСИМАЛЬНОЕ значение для объекта за дату"""
    object_name = sanitize_object_name(object_name)
    
    if target_date is None:
        target_date = datetime.now()
    
    date_str = target_date.strftime('%Y-%m-%d')
    now_str = datetime.now().isoformat()
    is_high_int = 1 if is_high else 0
    
    if count == 0:
        return delete_requirement(object_name, target_date)
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT max_count, is_high FROM requirement_history WHERE object_name = ? AND date = ?', 
            (object_name, date_str)
        )
        row = cursor.fetchone()
        
        if row:
            existing_count, existing_is_high = row
            if count > existing_count or (is_high and not existing_is_high):
                cursor.execute('''
                    UPDATE requirement_history
                    SET max_count = ?, is_high = ?, updated_at = ?
                    WHERE object_name = ? AND date = ?
                ''', (count, is_high_int, now_str, object_name, date_str))
                conn.commit()
                logger.debug(f"Обновлен объект {object_name} за {date_str}: {count} (было {existing_count})")
            conn.close()
            return True
        else:
            cursor.execute('''
                INSERT INTO requirement_history (object_name, date, max_count, is_high, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (object_name, date_str, count, is_high_int, now_str))
            conn.commit()
            conn.close()
            logger.debug(f"Создан объект {object_name} за {date_str}: {count}")
            return True
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении requirements: {e}")
        return False

def delete_requirement(object_name, target_date):
    """Удаляет запись о потребности за конкретную дату"""
    object_name = sanitize_object_name(object_name)
    date_str = target_date.strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM requirement_history WHERE object_name = ? AND date = ?', (object_name, date_str))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted:
            logger.debug(f"Удален объект {object_name} за {date_str}")
        return deleted
    except Exception as e:
        logger.error(f"Ошибка при удалении записи: {e}")
        return 0

def get_max_requirement(object_name, target_date):
    """Получает максимальное значение для объекта за дату"""
    object_name = sanitize_object_name(object_name)
    date_str = target_date.strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT max_count, is_high FROM requirement_history WHERE object_name = ? AND date = ?', (object_name, date_str))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'count': row[0], 'is_high': bool(row[1])}
        return {'count': 0, 'is_high': False}
    except Exception as e:
        logger.error(f"Ошибка при получении requirements: {e}")
        return {'count': 0, 'is_high': False}

def get_all_max_requirements(target_date):
    """Получает все максимальные потребности за дату в виде словаря"""
    date_str = target_date.strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT object_name, max_count, is_high FROM requirement_history WHERE date = ?', (date_str,))
        rows = cursor.fetchall()
        conn.close()
        
        result = {}
        for name, count, is_high in rows:
            result[name] = {'count': count, 'is_high': bool(is_high)}
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении всех requirements: {e}")
        return {}

def get_all_dates():
    """Получает все даты, за которые есть данные"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT date FROM requirement_history ORDER BY date DESC')
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при получении списка дат: {e}")
        return []

def cleanup_old_records(days=30):
    """Удаляет записи старше указанного количества дней"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        cursor.execute('DELETE FROM requirement_history WHERE date < ?', (cutoff_date,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        logger.info(f"Очищено {deleted_count} старых записей (старше {days} дней)")
        return deleted_count
    except Exception as e:
        logger.error(f"Ошибка при очистке старых записей: {e}")
        return 0

def get_last_updates():
    """Получает информацию о последних обновлениях в БД"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT date, COUNT(*) as cnt, MAX(updated_at) as last_update
            FROM requirement_history 
            GROUP BY date 
            ORDER BY date DESC 
            LIMIT 10
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        result = "Дата | Кол-во объектов | Последнее обновление\n"
        result += "-" * 60 + "\n"
        for row in rows:
            result += f"{row[0]} | {row[1]} | {row[2]}\n"
        return result
    except Exception as e:
        return f"Ошибка при получении информации об обновлениях: {e}"

# ========== ФУНКЦИИ ДЛЯ ПРОЕКТА 2 (Настройки объектов) ==========

def init_objects_settings():
    """Инициализирует настройки объектов из базовой структуры"""
    from config import OBJECTS_BASE
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        for obj in OBJECTS_BASE:
            cursor.execute('''
                INSERT OR IGNORE INTO objects_settings (id, name, visible, priority)
                VALUES (?, ?, ?, ?)
            ''', (obj['id'], obj['name'], 1, 0))
        
        conn.commit()
        conn.close()
        logger.info(f"Инициализированы настройки для {len(OBJECTS_BASE)} объектов")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации настроек объектов: {e}")
        return False

def get_objects_settings():
    """Получает все настройки объектов"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, visible, priority FROM objects_settings ORDER BY id')
        rows = cursor.fetchall()
        conn.close()
        return [{'id': row[0], 'name': row[1], 'visible': bool(row[2]), 'priority': bool(row[3])} for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при получении настроек объектов: {e}")
        return []

def update_object_settings(object_id, visible, priority):
    """Обновляет настройки объекта"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE objects_settings 
            SET visible = ?, priority = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (1 if visible else 0, 1 if priority else 0, object_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек объекта: {e}")
        return False

def get_global_order():
    """Получает глобальный порядок объектов"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT object_order FROM global_objects_order WHERE id = 1')
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении глобального порядка: {e}")
        return None

def save_global_order(order_list):
    """Сохраняет глобальный порядок объектов"""
    try:
        if not isinstance(order_list, list):
            raise ValueError("Order must be a list")
        for item in order_list:
            if not isinstance(item, int):
                raise ValueError("Order items must be integers")
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO global_objects_order (id, object_order, updated_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                object_order = excluded.object_order,
                updated_at = CURRENT_TIMESTAMP
        ''', (json.dumps(order_list),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении глобального порядка: {e}")
        return False