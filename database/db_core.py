# database/db_core.py
# -*- coding: utf-8 -*-
import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_NAME = 'requirements.db'

def get_db_connection():
    """Возвращает соединение с базой данных"""
    return sqlite3.connect(DB_NAME)


def init_db():
    """Создаёт таблицы, если их нет"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
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
                region TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Добавляем колонку region для существующих таблиц
        try:
            cursor.execute('ALTER TABLE objects_settings ADD COLUMN region TEXT DEFAULT ""')
        except sqlite3.OperationalError:
            # Колонка уже существует
            pass
        
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
                module_name TEXT NOT NULL CHECK(module_name IN ('dashboard', 'selection', 'worker_status')),
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
        
        # ========== ТАБЛИЦЫ ДЛЯ ВАКАНСИЙ (ПЛАН НА ДАТУ) ==========
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
        
        # ========== ТАБЛИЦЫ ДЛЯ ТЕКУЩИХ ПОТРЕБНОСТЕЙ ==========
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
        
        # ========== ТАБЛИЦА ПАСПОРТОВ ОБЪЕКТОВ ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS object_passports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL UNIQUE,
                address_production TEXT,
                address_hostel TEXT,
                operation_rate TEXT,
                requirements TEXT,
                functionality TEXT,
                free_meals TEXT,
                free_accommodation TEXT,
                salary_payment TEXT,
                local_work TEXT,
                part_time TEXT,
                deductions TEXT,
                features TEXT,
                work_schedule TEXT,
                documents_required TEXT,
                route_sheet_filename TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (object_id) REFERENCES objects_settings(id) ON DELETE CASCADE
            )
        ''')
        
        # ========== НОВАЯ ТАБЛИЦА ДЛЯ МНОЖЕСТВЕННЫХ МАРШРУТНЫХ ЛИСТОВ ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS object_route_sheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_size INTEGER,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                uploaded_by INTEGER,
                FOREIGN KEY (object_id) REFERENCES objects_settings(id) ON DELETE CASCADE,
                FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        
        # ========== ТАБЛИЦА ЕЖЕДНЕВНЫХ СНИПШОТОВ ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                object_name TEXT NOT NULL,
                office_name TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                plan INTEGER DEFAULT 0,
                is_high INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, object_name, office_name)
            )
        ''')
        
        # ========== ТАБЛИЦА СТАТУСОВ ВАХТОВИКОВ ==========
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS worker_statuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL UNIQUE,
                worker_full_name TEXT NOT NULL,
                agent_full_name TEXT NOT NULL,
                deal_date TEXT NOT NULL,
                check_in_date TEXT,
                shift_1_date TEXT,
                shift_5_date TEXT,
                last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_passports_object_id ON object_passports (object_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_date ON daily_snapshots (date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_object ON daily_snapshots (object_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_worker_agent ON worker_statuses (agent_full_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_worker_deal_date ON worker_statuses (deal_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_worker_lead_id ON worker_statuses (lead_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_route_sheets_object ON object_route_sheets (object_id)')
        
        conn.commit()
        
        # Создаём системного администратора по умолчанию
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
                VALUES (?, 'dashboard', 1), (?, 'selection', 1), (?, 'worker_status', 1)
            ''', (admin_id, admin_id, admin_id))
            
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


def init_objects_settings():
    """Инициализирует настройки объектов из конфига"""
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
            region = obj.get('region', '')
            
            cursor.execute('''
                INSERT OR IGNORE INTO objects_settings 
                (id, name, visible, priority, age_min, age_max, 
                 allowed_genders, allowed_nationalities, allows_conviction, link, region)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                obj_id, obj_name, 1, 0,
                age_min, age_max, 
                genders_str, nationalities_str, 
                allows_conviction, link, region
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Инициализированы настройки для {len(OBJECTS_BASE)} объектов")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации настроек объектов: {e}", exc_info=True)
        return False


def init_vacancy_tables():
    """Инициализирует таблицы вакансий (уже созданы в init_db)"""
    return True


def init_current_requirements_table():
    """Создаёт таблицу для текущих потребностей (уже создана в init_db)"""
    return True


def init_passports_table():
    """Создаёт таблицу паспортов объектов (уже создана в init_db)"""
    return True


def init_daily_snapshots_table():
    """Создаёт таблицу ежедневных снапшотов (уже создана в init_db)"""
    return True