# database.py
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timedelta
import logging
import json
import re

# Для Windows убираем time.tzset()
# Просто используем datetime.now() без изменения часового пояса
# Часовой пояс будет определяться на уровне приложения через передачу даты с фронтенда

logger = logging.getLogger(__name__)

DB_NAME = 'requirements.db'

# ... остальной код database.py без изменений ...

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
        
        # Таблица для настроек объектов с расширенными полями
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objects_settings (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                visible INTEGER DEFAULT 1,
                priority INTEGER DEFAULT 0,
                age_min INTEGER DEFAULT 18,
                age_max INTEGER DEFAULT 55,
                allowed_genders TEXT DEFAULT 'мужчина,женщина',
                allowed_nationalities TEXT DEFAULT 'РФ',
                allows_conviction INTEGER DEFAULT 0,
                link TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Проверяем существование новых колонок и добавляем их, если их нет
        cursor.execute("PRAGMA table_info(objects_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'age_min' not in columns:
            cursor.execute("ALTER TABLE objects_settings ADD COLUMN age_min INTEGER DEFAULT 18")
        if 'age_max' not in columns:
            cursor.execute("ALTER TABLE objects_settings ADD COLUMN age_max INTEGER DEFAULT 55")
        if 'allowed_genders' not in columns:
            cursor.execute("ALTER TABLE objects_settings ADD COLUMN allowed_genders TEXT DEFAULT 'мужчина,женщина'")
        if 'allowed_nationalities' not in columns:
            cursor.execute("ALTER TABLE objects_settings ADD COLUMN allowed_nationalities TEXT DEFAULT 'РФ'")
        if 'allows_conviction' not in columns:
            cursor.execute("ALTER TABLE objects_settings ADD COLUMN allows_conviction INTEGER DEFAULT 0")
        if 'link' not in columns:
            cursor.execute("ALTER TABLE objects_settings ADD COLUMN link TEXT")
        
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
            # Безопасно получаем значения с дефолтными
            obj_id = obj.get('id', 0)
            obj_name = obj.get('name', '')
            
            # Проверяем, существует ли уже объект
            cursor.execute('SELECT id FROM objects_settings WHERE id = ?', (obj_id,))
            if cursor.fetchone():
                continue  # Пропускаем, если уже есть
            
            # Безопасно получаем остальные поля
            age_min = obj.get('ageMin', 18)
            age_max = obj.get('ageMax', 55)
            
            allowed_genders = obj.get('allowedGenders', ['мужчина', 'женщина'])
            if isinstance(allowed_genders, list):
                genders_str = ','.join(allowed_genders)
            else:
                genders_str = str(allowed_genders)
            
            allowed_nationalities = obj.get('allowedNationalities', ['РФ'])
            if isinstance(allowed_nationalities, list):
                nationalities_str = ','.join(allowed_nationalities)
            else:
                nationalities_str = str(allowed_nationalities)
            
            allows_conviction = 1 if obj.get('allowsConviction', False) else 0
            link = obj.get('link', '')
            
            cursor.execute('''
                INSERT OR IGNORE INTO objects_settings 
                (id, name, visible, priority, age_min, age_max, 
                 allowed_genders, allowed_nationalities, allows_conviction, link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                obj_id, obj_name, 1, 0,
                age_min, age_max, 
                genders_str, nationalities_str, 
                allows_conviction, link
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Инициализированы настройки для {len(OBJECTS_BASE)} объектов")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации настроек объектов: {e}", exc_info=True)
        return False

def get_objects_settings():
    """Получает все настройки объектов (базовая версия)"""
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

def get_objects_settings_extended():
    """Получает все настройки объектов с расширенными полями"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, visible, priority, age_min, age_max, 
                   allowed_genders, allowed_nationalities, allows_conviction, link
            FROM objects_settings ORDER BY id
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        objects = []
        for row in rows:
            # Разбиваем строки обратно в списки
            genders_str = row[6] or 'мужчина,женщина'
            nationalities_str = row[7] or 'РФ'
            
            objects.append({
                'id': row[0],
                'name': row[1],
                'visible': bool(row[2]),
                'priority': bool(row[3]),
                'ageMin': row[4] or 18,
                'ageMax': row[5] or 55,
                'allowedGenders': [g.strip() for g in genders_str.split(',') if g.strip()],
                'allowedNationalities': [n.strip() for n in nationalities_str.split(',') if n.strip()],
                'allowsConviction': bool(row[8]),
                'link': row[9] or ''
            })
        return objects
    except Exception as e:
        logger.error(f"Ошибка при получении настроек объектов: {e}")
        return []

def update_object_settings(object_id, visible, priority):
    """Обновляет базовые настройки объекта"""
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

def create_object_extended(name, age_min, age_max, allowed_genders, allowed_nationalities, 
                           allows_conviction, link='', visible=True, priority=False):
    """Создаёт новый объект с расширенными полями"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Получаем следующий ID
        cursor.execute('SELECT MAX(id) FROM objects_settings')
        max_id = cursor.fetchone()[0]
        new_id = (max_id or 0) + 1
        
        # Преобразуем списки в строки
        genders_str = ','.join(allowed_genders) if isinstance(allowed_genders, list) else allowed_genders
        nationalities_str = ','.join(allowed_nationalities) if isinstance(allowed_nationalities, list) else allowed_nationalities
        
        # Добавляем в objects_settings
        cursor.execute('''
            INSERT INTO objects_settings (id, name, visible, priority, age_min, age_max, 
                                         allowed_genders, allowed_nationalities, allows_conviction, link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (new_id, name, 1 if visible else 0, 1 if priority else 0,
              age_min, age_max, genders_str, nationalities_str, 
              1 if allows_conviction else 0, link))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Создан новый объект: {name} (ID: {new_id})")
        return new_id
    except sqlite3.IntegrityError:
        logger.warning(f"Объект с именем {name} уже существует")
        return None
    except Exception as e:
        logger.error(f"Ошибка при создании объекта: {e}")
        return None

def update_object_settings_full(object_id, updates):
    """Обновляет все настройки объекта"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Формируем SQL запрос динамически
        fields = []
        params = []
        
        field_mapping = {
            'name': 'name',
            'visible': 'visible',
            'priority': 'priority',
            'age_min': 'age_min',
            'age_max': 'age_max',
            'allowed_genders': 'allowed_genders',
            'allowed_nationalities': 'allowed_nationalities',
            'allows_conviction': 'allows_conviction',
            'link': 'link'
        }
        
        for key, db_field in field_mapping.items():
            if key in updates:
                fields.append(f"{db_field} = ?")
                value = updates[key]
                if key in ['visible', 'priority', 'allows_conviction']:
                    value = 1 if value else 0
                elif key in ['allowed_genders', 'allowed_nationalities']:
                    value = ','.join(value) if isinstance(value, list) else value
                params.append(value)
        
        if not fields:
            return True
            
        params.append(object_id)
        query = f"UPDATE objects_settings SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(query, params)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Обновлён объект ID {object_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении объекта: {e}")
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
    
# ========== ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ОБЪЕКТАМИ (CRUD) ==========

def get_object_by_id(object_id):
    """Получает объект по ID с расширенными полями"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, visible, priority, age_min, age_max, 
                   allowed_genders, allowed_nationalities, allows_conviction, link
            FROM objects_settings WHERE id = ?
        ''', (object_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            genders_str = row[6] or 'мужчина,женщина'
            nationalities_str = row[7] or 'РФ'
            
            return {
                'id': row[0],
                'name': row[1],
                'visible': bool(row[2]),
                'priority': bool(row[3]),
                'ageMin': row[4] or 18,
                'ageMax': row[5] or 55,
                'allowedGenders': [g.strip() for g in genders_str.split(',') if g.strip()],
                'allowedNationalities': [n.strip() for n in nationalities_str.split(',') if n.strip()],
                'allowsConviction': bool(row[8]),
                'link': row[9] or ''
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении объекта: {e}")
        return None

def get_objects_base():
    """Получает все объекты из objects_settings"""
    return get_objects_settings()

def create_object(name, age_min, age_max, allowed_genders, allowed_nationalities, 
                  allows_conviction, link='', visible=True, priority=False):
    """Создаёт новый объект (совместимость со старым API)"""
    return create_object_extended(name, age_min, age_max, allowed_genders, allowed_nationalities,
                                  allows_conviction, link, visible, priority)

def update_object_settings_extended(object_id, updates):
    """Обновляет настройки объекта с дополнительными полями (совместимость)"""
    return update_object_settings_full(object_id, updates)

def delete_object(object_id):
    """Удаляет объект из БД"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Удаляем права доступа к объекту
        cursor.execute('DELETE FROM user_object_permissions WHERE object_id = ?', (object_id,))
        # Удаляем настройки объекта
        cursor.execute('DELETE FROM objects_settings WHERE id = ?', (object_id,))
        
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        if deleted:
            logger.info(f"Удалён объект {object_id}")
        return deleted > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении объекта: {e}")
        return False

# ========== ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ВАКАНСИЯМИ (НОВАЯ СИСТЕМА) ==========

def init_vacancy_tables():
    """Создаёт таблицы для хранения вакансий"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Таблица объектов вакансий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vacancy_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица должностей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vacancy_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (object_id) REFERENCES vacancy_objects(id) ON DELETE CASCADE,
                UNIQUE(object_id, name)
            )
        ''')
        
        # Таблица с количествами по должностям
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vacancy_requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                rf_men INTEGER DEFAULT 0,
                rf_women INTEGER DEFAULT 0,
                rf_family INTEGER DEFAULT 0,
                cis_men INTEGER DEFAULT 0,
                cis_women INTEGER DEFAULT 0,
                cis_family INTEGER DEFAULT 0,
                is_high INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (position_id) REFERENCES vacancy_positions(id) ON DELETE CASCADE,
                UNIQUE(position_id, date)
            )
        ''')
        
        # Индексы
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vacancy_date ON vacancy_requirements (date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vacancy_position ON vacancy_requirements (position_id)')
        
        conn.commit()
        conn.close()
        logger.info("✅ Таблицы для вакансий созданы")
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц вакансий: {e}")
        return False


def get_all_vacancy_data(date=None):
    """
    Получает все данные о вакансиях за указанную дату
    Возвращает структуру, аналогичную старой из Google Sheets
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Получаем все объекты
        cursor.execute('SELECT id, name FROM vacancy_objects ORDER BY name')
        objects = cursor.fetchall()
        
        result = {}
        
        for obj_id, obj_name in objects:
            # Получаем все должности объекта
            cursor.execute('''
                SELECT id, name FROM vacancy_positions 
                WHERE object_id = ? 
                ORDER BY name
            ''', (obj_id,))
            positions = cursor.fetchall()
            
            obj_data = {
                'rf': {'men': 0, 'women': 0, 'family': 0},
                'cis': {'men': 0, 'women': 0, 'family': 0},
                'positions': [],
                'is_high': False
            }
            
            for pos_id, pos_name in positions:
                # Получаем данные за указанную дату
                cursor.execute('''
                    SELECT rf_men, rf_women, rf_family, cis_men, cis_women, cis_family, is_high
                    FROM vacancy_requirements
                    WHERE position_id = ? AND date = ?
                ''', (pos_id, date))
                req = cursor.fetchone()
                
                if req:
                    pos_data = {
                        'name': pos_name,
                        'rf': {'men': req[0], 'women': req[1], 'family': req[2]},
                        'cis': {'men': req[3], 'women': req[4], 'family': req[5]},
                        'is_high': bool(req[6])
                    }
                    # Суммируем в общие итоги
                    obj_data['rf']['men'] += req[0]
                    obj_data['rf']['women'] += req[1]
                    obj_data['rf']['family'] += req[2]
                    obj_data['cis']['men'] += req[3]
                    obj_data['cis']['women'] += req[4]
                    obj_data['cis']['family'] += req[5]
                    
                    # Если хоть одна должность имеет is_high, то и объект имеет приоритет
                    if bool(req[6]):
                        obj_data['is_high'] = True
                else:
                    pos_data = {
                        'name': pos_name,
                        'rf': {'men': 0, 'women': 0, 'family': 0},
                        'cis': {'men': 0, 'women': 0, 'family': 0},
                        'is_high': False
                    }
                
                obj_data['positions'].append(pos_data)
            
            result[obj_name] = obj_data
        
        conn.close()
        
        # Отладочный вывод
        for obj_name, obj_data in result.items():
            if obj_data['is_high']:
                print(f"DEBUG: {obj_name} has is_high=True")
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при получении данных вакансий: {e}")
        return {}


def get_plan_requirements_for_date(target_date):
    """
    Получает суммарный план (потребность) по всем объектам за указанную дату
    из таблиц vacancy_requirements
    Возвращает словарь: {объект: {'count': сумма, 'is_high': приоритет}}
    """
    if isinstance(target_date, str):
        date_str = target_date
    else:
        date_str = target_date.strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Получаем суммарные потребности по объектам
        cursor.execute('''
            SELECT vo.name, 
                   SUM(vr.rf_men + vr.rf_women + vr.rf_family + 
                       vr.cis_men + vr.cis_women + vr.cis_family) as total_count,
                   MAX(vr.is_high) as is_high
            FROM vacancy_objects vo
            JOIN vacancy_positions vp ON vp.object_id = vo.id
            JOIN vacancy_requirements vr ON vr.position_id = vp.id
            WHERE vr.date = ?
            GROUP BY vo.id, vo.name
        ''', (date_str,))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = {}
        for name, count, is_high in rows:
            if count > 0:
                result[name] = {
                    'count': count,
                    'is_high': bool(is_high)
                }
        
        logger.info(f"📊 Получен план из БД за {date_str}: {len(result)} объектов, всего {sum(r['count'] for r in result.values())} чел.")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при получении плана из БД: {e}")
        return {}


def save_vacancy_object(name):
    """Создаёт новый объект вакансии"""
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30)
        cursor = conn.cursor()
        
        # Сначала проверяем, существует ли уже такой объект
        cursor.execute('SELECT id FROM vacancy_objects WHERE name = ?', (name,))
        existing = cursor.fetchone()
        if existing:
            logger.warning(f"Объект {name} уже существует (ID: {existing[0]})")
            conn.close()
            return None  # Возвращаем None если объект уже есть
        
        # Если нет - создаём
        cursor.execute('INSERT INTO vacancy_objects (name) VALUES (?)', (name,))
        obj_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"✅ Создан объект вакансии: {name} (ID: {obj_id})")
        return obj_id
    except sqlite3.IntegrityError:
        logger.warning(f"Объект {name} уже существует (IntegrityError)")
        return None
    except Exception as e:
        logger.error(f"Ошибка при создании объекта: {e}")
        return None


def delete_vacancy_object(object_name):
    """Удаляет объект вакансии и все связанные данные"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM vacancy_objects WHERE name = ?', (object_name,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted:
            logger.info(f"🗑️ Удалён объект вакансии: {object_name}")
        return deleted > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении объекта: {e}")
        return False


def save_vacancy_position(object_name, position_name):
    """Добавляет должность к объекту"""
    try:
        conn = sqlite3.connect(DB_NAME, timeout=30)
        cursor = conn.cursor()
        
        # Получаем ID объекта
        cursor.execute('SELECT id FROM vacancy_objects WHERE name = ?', (object_name,))
        obj = cursor.fetchone()
        if not obj:
            conn.close()
            return None
        
        obj_id = obj[0]
        
        # Проверяем, существует ли уже такая должность
        cursor.execute('SELECT id FROM vacancy_positions WHERE object_id = ? AND name = ?', (obj_id, position_name))
        existing = cursor.fetchone()
        if existing:
            logger.warning(f"Должность {position_name} уже существует (ID: {existing[0]})")
            conn.close()
            return None
        
        # Добавляем должность
        cursor.execute('''
            INSERT INTO vacancy_positions (object_id, name) VALUES (?, ?)
        ''', (obj_id, position_name))
        pos_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"✅ Добавлена должность: {position_name} к объекту {object_name}")
        return pos_id
    except sqlite3.IntegrityError:
        logger.warning(f"Должность {position_name} уже существует (IntegrityError)")
        return None
    except Exception as e:
        logger.error(f"Ошибка при добавлении должности: {e}")
        return None


def delete_vacancy_position(object_name, position_name):
    """Удаляет должность"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM vacancy_positions 
            WHERE object_id = (SELECT id FROM vacancy_objects WHERE name = ?)
            AND name = ?
        ''', (object_name, position_name))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted:
            logger.info(f"🗑️ Удалена должность: {position_name} из объекта {object_name}")
        return deleted > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении должности: {e}")
        return False


def save_vacancy_requirements_batch(object_name, date, requirements):
    """
    Сохраняет все потребности для объекта за дату
    requirements: список словарей с данными должностей
    """
    try:
        print(f"=== СОХРАНЕНИЕ ДЛЯ {object_name}, ДАТА {date} ===")
        print(f"is_high в requirements: {[req.get('is_high', False) for req in requirements]}")
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Получаем ID объекта
        cursor.execute('SELECT id FROM vacancy_objects WHERE name = ?', (object_name,))
        obj = cursor.fetchone()
        if not obj:
            print(f"❌ Объект {object_name} не найден в vacancy_objects")
            return False
        obj_id = obj[0]
        
        saved_count = 0
        
        for req in requirements:
            position_name = req.get('name')
            if not position_name:
                continue
            
            # Получаем ID должности
            cursor.execute('''
                SELECT id FROM vacancy_positions 
                WHERE object_id = ? AND name = ?
            ''', (obj_id, position_name))
            pos = cursor.fetchone()
            if not pos:
                print(f"⚠️ Должность {position_name} не найдена для объекта {object_name}")
                continue
            pos_id = pos[0]
            
            is_high_value = 1 if req.get('is_high', False) else 0
            print(f"  Должность: {position_name}, is_high={is_high_value}")
            
            # Сохраняем данные
            cursor.execute('''
                INSERT INTO vacancy_requirements 
                (position_id, date, rf_men, rf_women, rf_family, cis_men, cis_women, cis_family, is_high)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(position_id, date) DO UPDATE SET
                    rf_men = excluded.rf_men,
                    rf_women = excluded.rf_women,
                    rf_family = excluded.rf_family,
                    cis_men = excluded.cis_men,
                    cis_women = excluded.cis_women,
                    cis_family = excluded.cis_family,
                    is_high = excluded.is_high,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                pos_id, date,
                req.get('rf', {}).get('men', 0),
                req.get('rf', {}).get('women', 0),
                req.get('rf', {}).get('family', 0),
                req.get('cis', {}).get('men', 0),
                req.get('cis', {}).get('women', 0),
                req.get('cis', {}).get('family', 0),
                is_high_value
            ))
            saved_count += 1
        
        conn.commit()
        conn.close()
        print(f"✅ Сохранено {saved_count} должностей для объекта {object_name}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при сохранении потребностей: {e}")
        logger.error(f"Ошибка при сохранении потребностей: {e}")
        return False


def migrate_from_google_sheets():
    """
    Миграция: переносит данные из Google Sheets в БД (одноразово)
    """
    try:
        # Инициализируем таблицы
        init_vacancy_tables()
        
        # Получаем данные из Google Sheets
        from google_sheets import GoogleSheetsAPI
        google_api = GoogleSheetsAPI()
        vacancy_data = google_api.get_vacancy_data()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        for obj_name, obj_data in vacancy_data.items():
            # Создаём объект
            obj_id = save_vacancy_object(obj_name)
            if not obj_id:
                continue
            
            # Создаём должности и сохраняем данные
            for pos in obj_data.get('positions', []):
                pos_id = save_vacancy_position(obj_name, pos['name'])
                
                if pos_id:
                    # Сохраняем данные за сегодня
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO vacancy_requirements 
                        (position_id, date, rf_men, rf_women, rf_family, cis_men, cis_women, cis_family, is_high)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        pos_id, today,
                        pos['rf']['men'], pos['rf']['women'], pos['rf']['family'],
                        pos['cis']['men'], pos['cis']['women'], pos['cis']['family'],
                        0
                    ))
                    conn.commit()
                    conn.close()
        
        logger.info("✅ Миграция из Google Sheets завершена")
        return True
    except Exception as e:
        logger.error(f"Ошибка при миграции: {e}")
        return False


# ========== АВТОМАТИЧЕСКИЙ ПЕРЕНОС ПОТРЕБНОСТЕЙ ==========

def copy_requirements_from_previous_day(target_date):
    """
    Копирует потребности с предыдущего дня на указанную дату,
    если за указанную дату нет данных.
    
    Args:
        target_date: строка в формате 'YYYY-MM-DD' или datetime
    
    Returns:
        int: количество скопированных записей
    """
    from datetime import datetime, timedelta
    
    if isinstance(target_date, str):
        target_date_str = target_date
        target_date_obj = datetime.strptime(target_date, '%Y-%m-%d')
    else:
        target_date_str = target_date.strftime('%Y-%m-%d')
        target_date_obj = target_date
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже данные за эту дату
        cursor.execute('SELECT COUNT(*) FROM vacancy_requirements WHERE date = ?', (target_date_str,))
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            logger.info(f"📋 Данные за {target_date_str} уже существуют ({existing_count} записей)")
            conn.close()
            return 0
        
        # Ищем предыдущий день с данными
        previous_date = target_date_obj - timedelta(days=1)
        copied_count = 0
        max_days_back = 30  # Ищем максимум за 30 дней назад
        
        for days_back in range(1, max_days_back + 1):
            prev_date_str = previous_date.strftime('%Y-%m-%d')
            
            cursor.execute('SELECT COUNT(*) FROM vacancy_requirements WHERE date = ?', (prev_date_str,))
            has_data = cursor.fetchone()[0] > 0
            
            if has_data:
                logger.info(f"📋 Найден предыдущий день с данными: {prev_date_str}")
                
                # Копируем все записи с предыдущего дня
                cursor.execute('''
                    INSERT INTO vacancy_requirements 
                    (position_id, date, rf_men, rf_women, rf_family, cis_men, cis_women, cis_family, is_high)
                    SELECT position_id, ?, rf_men, rf_women, rf_family, cis_men, cis_women, cis_family, is_high
                    FROM vacancy_requirements
                    WHERE date = ?
                ''', (target_date_str, prev_date_str))
                
                copied_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"✅ Скопировано {copied_count} записей потребностей с {prev_date_str} на {target_date_str}")
                break
            
            previous_date -= timedelta(days=1)
        
        conn.close()
        
        if copied_count == 0:
            logger.info(f"⚠️ Не найдено предыдущих дней с данными для копирования на {target_date_str}")
        
        return copied_count
        
    except Exception as e:
        logger.error(f"Ошибка при копировании потребностей: {e}", exc_info=True)
        return 0