# database.py - ПОЛНАЯ ВЕРСИЯ С ТАБЛИЦЕЙ ТЕКУЩИХ ПОТРЕБНОСТЕЙ
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timedelta
import logging
import json
import re

logger = logging.getLogger(__name__)

DB_NAME = 'requirements.db'


def init_db():
    """Создает таблицы, если их нет"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # ========== ТАБЛИЦЫ ДЛЯ ТЕКУЩИХ ПОТРЕБНОСТЕЙ (ПОДБОР ОБЪЕКТОВ) ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS current_requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_name TEXT NOT NULL,
                position_name TEXT NOT NULL,
                rf_men INTEGER DEFAULT 0,
                rf_women INTEGER DEFAULT 0,
                rf_family INTEGER DEFAULT 0,
                cis_men INTEGER DEFAULT 0,
                cis_women INTEGER DEFAULT 0,
                cis_family INTEGER DEFAULT 0,
                is_high INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(object_name, position_name)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_current_req_object ON current_requirements (object_name)')
        
        # ========== ТАБЛИЦЫ ДЛЯ ВАКАНСИЙ (ПЛАН НА ДАТУ ДЛЯ ДАШБОРДА) ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vacancy_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
        
        # ========== ТАБЛИЦЫ ДЛЯ НАСТРОЕК ОБЪЕКТОВ ==========
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_objects_order (
                id INTEGER PRIMARY KEY DEFAULT 1,
                object_order TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ========== ТАБЛИЦЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ==========
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_avatars (
                user_id INTEGER PRIMARY KEY,
                avatar_filename TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Индексы
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_current_req_object ON current_requirements (object_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vacancy_date ON vacancy_requirements (date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vacancy_position ON vacancy_requirements (position_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_objects_visible ON objects_settings (visible)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_objects_priority ON objects_settings (priority)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users (username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users (role)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_module_perms_user ON user_module_permissions (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_object_perms_user ON user_object_permissions (user_id)')
        
        conn.commit()
        
        # Создаем системного администратора по умолчанию
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
            
            cursor.execute('''
                INSERT INTO user_module_permissions (user_id, module_name, can_view)
                VALUES (?, 'dashboard', 1), (?, 'selection', 1)
            ''', (admin_id, admin_id))
            
            cursor.execute('SELECT id FROM objects_settings')
            all_objects = cursor.fetchall()
            for obj in all_objects:
                cursor.execute('''
                    INSERT INTO user_object_permissions (user_id, object_id, can_view_dashboard, can_view_selection)
                    VALUES (?, ?, 1, 1)
                ''', (admin_id, obj[0]))
            
            conn.commit()
            logger.info("✅ Системный администратор создан (ID=1, логин: admin, пароль: admin123)")
        
        conn.close()
        logger.info(f"База данных {DB_NAME} инициализирована")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}")
        return False


# ========== ФУНКЦИИ ДЛЯ ТЕКУЩИХ ПОТРЕБНОСТЕЙ (ПОДБОР ОБЪЕКТОВ) ==========

def init_current_requirements_table():
    """Создаёт таблицу для текущих потребностей (без привязки к дате)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS current_requirements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_name TEXT NOT NULL,
                position_name TEXT NOT NULL,
                rf_men INTEGER DEFAULT 0,
                rf_women INTEGER DEFAULT 0,
                rf_family INTEGER DEFAULT 0,
                cis_men INTEGER DEFAULT 0,
                cis_women INTEGER DEFAULT 0,
                cis_family INTEGER DEFAULT 0,
                is_high INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(object_name, position_name)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_current_req_object ON current_requirements (object_name)')
        
        conn.commit()
        conn.close()
        logger.info("✅ Таблица текущих потребностей создана")
        return True
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы текущих потребностей: {e}")
        return False


def get_current_requirements():
    """Получает все текущие потребности (без привязки к дате) - оптимизированная версия"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT object_name, position_name, 
                   rf_men, rf_women, rf_family,
                   cis_men, cis_women, cis_family,
                   is_high
            FROM current_requirements
            ORDER BY object_name, position_name
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        result = {}
        for row in rows:
            obj_name = row['object_name']
            pos_name = row['position_name']
            
            if obj_name not in result:
                result[obj_name] = {
                    'rf': {'men': 0, 'women': 0, 'family': 0},
                    'cis': {'men': 0, 'women': 0, 'family': 0},
                    'positions': [],
                    'is_high': bool(row['is_high'])
                }
            
            pos_data = {
                'name': pos_name,
                'rf': {
                    'men': row['rf_men'] or 0, 
                    'women': row['rf_women'] or 0, 
                    'family': row['rf_family'] or 0
                },
                'cis': {
                    'men': row['cis_men'] or 0, 
                    'women': row['cis_women'] or 0, 
                    'family': row['cis_family'] or 0
                }
            }
            
            result[obj_name]['positions'].append(pos_data)
            result[obj_name]['rf']['men'] += pos_data['rf']['men']
            result[obj_name]['rf']['women'] += pos_data['rf']['women']
            result[obj_name]['rf']['family'] += pos_data['rf']['family']
            result[obj_name]['cis']['men'] += pos_data['cis']['men']
            result[obj_name]['cis']['women'] += pos_data['cis']['women']
            result[obj_name]['cis']['family'] += pos_data['cis']['family']
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении текущих потребностей: {e}")
        return {}


def save_current_requirements(objects_data):
    """Сохраняет текущие потребности (заменяет все существующие)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Очищаем старые данные
        cursor.execute('DELETE FROM current_requirements')
        
        # Сохраняем новые
        for obj_name, obj_data in objects_data.items():
            is_high = 1 if obj_data.get('is_high', False) else 0
            
            for pos in obj_data.get('positions', []):
                pos_name = pos.get('name', '')
                if not pos_name:
                    continue
                
                cursor.execute('''
                    INSERT INTO current_requirements 
                    (object_name, position_name, rf_men, rf_women, rf_family,
                     cis_men, cis_women, cis_family, is_high)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    obj_name, pos_name,
                    pos.get('rf', {}).get('men', 0),
                    pos.get('rf', {}).get('women', 0),
                    pos.get('rf', {}).get('family', 0),
                    pos.get('cis', {}).get('men', 0),
                    pos.get('cis', {}).get('women', 0),
                    pos.get('cis', {}).get('family', 0),
                    is_high
                ))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Сохранены текущие потребности для {len(objects_data)} объектов")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении текущих потребностей: {e}")
        return False


def get_current_requirements_for_object(object_name):
    """Получает потребности для конкретного объекта"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT position_name, 
                   rf_men, rf_women, rf_family,
                   cis_men, cis_women, cis_family,
                   is_high
            FROM current_requirements
            WHERE object_name = ?
            ORDER BY position_name
        ''', (object_name,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        result = {
            'rf': {'men': 0, 'women': 0, 'family': 0},
            'cis': {'men': 0, 'women': 0, 'family': 0},
            'positions': [],
            'is_high': False
        }
        
        for row in rows:
            pos_data = {
                'name': row['position_name'],
                'rf': {
                    'men': row['rf_men'] or 0,
                    'women': row['rf_women'] or 0,
                    'family': row['rf_family'] or 0
                },
                'cis': {
                    'men': row['cis_men'] or 0,
                    'women': row['cis_women'] or 0,
                    'family': row['cis_family'] or 0
                }
            }
            result['positions'].append(pos_data)
            result['rf']['men'] += pos_data['rf']['men']
            result['rf']['women'] += pos_data['rf']['women']
            result['rf']['family'] += pos_data['rf']['family']
            result['cis']['men'] += pos_data['cis']['men']
            result['cis']['women'] += pos_data['cis']['women']
            result['cis']['family'] += pos_data['cis']['family']
            result['is_high'] = result['is_high'] or bool(row['is_high'])
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении потребностей объекта {object_name}: {e}")
        return None


# ========== ФУНКЦИИ ДЛЯ ВАКАНСИЙ (ПЛАН НА ДАТУ ДЛЯ ДАШБОРДА) ==========

def init_vacancy_tables():
    """Создаёт таблицы для хранения вакансий (уже созданы в init_db)"""
    return True


def get_all_vacancy_data(date=None):
    """Получает все данные о вакансиях за указанную дату"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, name FROM vacancy_objects ORDER BY name')
        objects = cursor.fetchall()
        
        result = {}
        
        for obj_id, obj_name in objects:
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
                    obj_data['rf']['men'] += req[0]
                    obj_data['rf']['women'] += req[1]
                    obj_data['rf']['family'] += req[2]
                    obj_data['cis']['men'] += req[3]
                    obj_data['cis']['women'] += req[4]
                    obj_data['cis']['family'] += req[5]
                    
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
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при получении данных вакансий: {e}")
        return {}


def get_plan_requirements_for_date(target_date):
    """Получает суммарный план (потребность) по всем объектам за указанную дату"""
    if isinstance(target_date, str):
        date_str = target_date
    else:
        date_str = target_date.strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
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
        
        cursor.execute('SELECT id FROM vacancy_objects WHERE name = ?', (name,))
        existing = cursor.fetchone()
        if existing:
            logger.warning(f"Объект {name} уже существует (ID: {existing[0]})")
            conn.close()
            return None
        
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
        
        cursor.execute('SELECT id FROM vacancy_objects WHERE name = ?', (object_name,))
        obj = cursor.fetchone()
        if not obj:
            conn.close()
            return None
        
        obj_id = obj[0]
        
        cursor.execute('SELECT id FROM vacancy_positions WHERE object_id = ? AND name = ?', (obj_id, position_name))
        existing = cursor.fetchone()
        if existing:
            logger.warning(f"Должность {position_name} уже существует (ID: {existing[0]})")
            conn.close()
            return None
        
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
    """Сохраняет все потребности для объекта за дату (для дашборда)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
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
            
            cursor.execute('''
                SELECT id FROM vacancy_positions 
                WHERE object_id = ? AND name = ?
            ''', (obj_id, position_name))
            pos = cursor.fetchone()
            if not pos:
                continue
            pos_id = pos[0]
            
            is_high_value = 1 if req.get('is_high', False) else 0
            
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
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении потребностей: {e}")
        return False


# ========== ФУНКЦИИ ДЛЯ НАСТРОЕК ОБЪЕКТОВ ==========

def init_objects_settings():
    from config import OBJECTS_BASE
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        for obj in OBJECTS_BASE:
            obj_id = obj.get('id', 0)
            obj_name = obj.get('name', '')
            
            cursor.execute('SELECT id FROM objects_settings WHERE id = ?', (obj_id,))
            if cursor.fetchone():
                continue
            
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
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT MAX(id) FROM objects_settings')
        max_id = cursor.fetchone()[0]
        new_id = (max_id or 0) + 1
        
        genders_str = ','.join(allowed_genders) if isinstance(allowed_genders, list) else allowed_genders
        nationalities_str = ','.join(allowed_nationalities) if isinstance(allowed_nationalities, list) else allowed_nationalities
        
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
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
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


def get_object_by_id(object_id):
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


def delete_object(object_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM user_object_permissions WHERE object_id = ?', (object_id,))
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


# ========== ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ==========

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
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Полностью удален пользователь {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {e}")
        return False


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


# ========== ФУНКЦИИ ДЛЯ ПРАВ ==========

def get_user_module_permissions(user_id):
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


# ========== ФУНКЦИИ ДЛЯ АУДИТА И ПРОФИЛЯ ==========

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