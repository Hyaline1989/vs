# database/objects.py
# -*- coding: utf-8 -*-
import sqlite3
import json
import logging

from database.db_core import DB_NAME

logger = logging.getLogger(__name__)


def get_objects_settings():
    """Получает базовые настройки объектов (id, name, visible, priority)"""
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
    """Получает расширенные настройки объектов (все поля)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, visible, priority, age_min, age_max, 
                   allowed_genders, allowed_nationalities, allows_conviction, link, region
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
                'link': row[9] or '',
                'region': row[10] or ''
            })
        return objects
    except Exception as e:
        logger.error(f"Ошибка при получении расширенных настроек объектов: {e}")
        return []


def get_object_by_id(object_id):
    """Получает объект по ID"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, visible, priority, age_min, age_max, 
                   allowed_genders, allowed_nationalities, allows_conviction, link, region
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
                'link': row[9] or '',
                'region': row[10] or ''
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении объекта: {e}")
        return None


def update_object_settings(object_id, visible, priority):
    """Обновляет видимость и приоритет объекта"""
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


def update_object_settings_full(object_id, updates):
    """Полное обновление объекта (все поля)"""
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
            'link': 'link',
            'region': 'region'
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


def create_object_extended(name, age_min, age_max, allowed_genders, allowed_nationalities, 
                           allows_conviction, link='', visible=True, priority=False, region=''):
    """Создаёт новый объект"""
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
                                         allowed_genders, allowed_nationalities, allows_conviction, link, region)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (new_id, name, 1 if visible else 0, 1 if priority else 0,
              age_min, age_max, genders_str, nationalities_str, 
              1 if allows_conviction else 0, link, region))
        
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


def delete_object(object_id):
    """Удаляет объект"""
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


# ========== ФУНКЦИИ ДЛЯ ПАСПОРТОВ ОБЪЕКТОВ ==========

def get_object_passport(object_id):
    """Получает паспорт объекта по его ID"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM object_passports WHERE object_id = ?
        ''', (object_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении паспорта объекта {object_id}: {e}")
        return None


def save_object_passport(object_id, passport_data):
    """Сохраняет или обновляет паспорт объекта"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже паспорт
        cursor.execute('SELECT id FROM object_passports WHERE object_id = ?', (object_id,))
        existing = cursor.fetchone()
        
        fields = [
            'address_production', 'address_hostel', 'operation_rate', 'requirements',
            'functionality', 'free_meals', 'free_accommodation', 'salary_payment',
            'local_work', 'part_time', 'deductions', 'features', 'work_schedule',
            'documents_required', 'contact_person'
        ]
        
        if existing:
            # Обновляем существующий
            set_clause = ', '.join([f"{field} = ?" for field in fields])
            set_clause += ', updated_at = CURRENT_TIMESTAMP'
            values = [passport_data.get(field, '') for field in fields]
            values.append(object_id)
            
            cursor.execute(f'''
                UPDATE object_passports 
                SET {set_clause}
                WHERE object_id = ?
            ''', values)
        else:
            # Вставляем новый
            placeholders = ', '.join(['?' for _ in fields])
            values = [object_id] + [passport_data.get(field, '') for field in fields]
            
            cursor.execute(f'''
                INSERT INTO object_passports (object_id, {', '.join(fields)})
                VALUES ({', '.join(['?'] + [placeholders])})
            ''', values)
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Сохранён паспорт для объекта ID {object_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении паспорта объекта {object_id}: {e}")
        return False


def update_route_sheet(object_id, filename):
    """Обновляет имя файла маршрутного листа для объекта (для обратной совместимости)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM object_passports WHERE object_id = ?', (object_id,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE object_passports 
                SET route_sheet_filename = ?, updated_at = CURRENT_TIMESTAMP
                WHERE object_id = ?
            ''', (filename, object_id))
        else:
            cursor.execute('''
                INSERT INTO object_passports (object_id, route_sheet_filename, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (object_id, filename))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Сохранён маршрутный лист для объекта ID {object_id}: {filename}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении маршрутного листа: {e}")
        return False


def get_route_sheet_filename(object_id):
    """Получает имя файла маршрутного листа (для обратной совместимости - возвращает первый)"""
    sheets = get_route_sheets(object_id)
    if sheets:
        return sheets[0]['filename']
    return None


def delete_route_sheet(object_id):
    """Удаляет информацию о маршрутном листе (для обратной совместимости)"""
    return delete_all_route_sheets(object_id)


# ========== НОВЫЕ ФУНКЦИИ ДЛЯ МНОЖЕСТВЕННЫХ МАРШРУТНЫХ ЛИСТОВ ==========

def get_route_sheets(object_id):
    """Получает список всех маршрутных листов для объекта"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, object_id, filename, original_name, file_size, uploaded_at, uploaded_by
            FROM object_route_sheets
            WHERE object_id = ?
            ORDER BY uploaded_at DESC
        ''', (object_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при получении маршрутных листов для объекта {object_id}: {e}")
        return []


def add_route_sheet(object_id, filename, original_name, file_size, uploaded_by=None):
    """Добавляет новый маршрутный лист для объекта"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Проверяем, не превышен ли лимит (5 файлов)
        cursor.execute('SELECT COUNT(*) FROM object_route_sheets WHERE object_id = ?', (object_id,))
        count = cursor.fetchone()[0]
        
        if count >= 5:
            conn.close()
            logger.warning(f"Превышен лимит маршрутных листов для объекта {object_id}")
            return None
        
        cursor.execute('''
            INSERT INTO object_route_sheets (object_id, filename, original_name, file_size, uploaded_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (object_id, filename, original_name, file_size, uploaded_by))
        
        sheet_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Добавлен маршрутный лист для объекта {object_id}: {original_name}")
        return sheet_id
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении маршрутного листа: {e}")
        return None


def delete_route_sheet_by_id(sheet_id):
    """Удаляет маршрутный лист по ID"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Получаем имя файла перед удалением
        cursor.execute('SELECT filename FROM object_route_sheets WHERE id = ?', (sheet_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
        
        filename = row[0]
        
        # Удаляем запись из БД
        cursor.execute('DELETE FROM object_route_sheets WHERE id = ?', (sheet_id,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted:
            # Удаляем физический файл
            try:
                from flask import current_app
                import os
                filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'route_sheets', filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"Удалён файл маршрутного листа: {filename}")
            except Exception as e:
                logger.error(f"Ошибка при удалении файла: {e}")
            
            logger.info(f"✅ Удалён маршрутный лист ID {sheet_id}")
        
        return deleted > 0
        
    except Exception as e:
        logger.error(f"Ошибка при удалении маршрутного листа: {e}")
        return False


def delete_all_route_sheets(object_id):
    """Удаляет все маршрутные листы для объекта"""
    try:
        # Получаем список файлов
        sheets = get_route_sheets(object_id)
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Удаляем записи из БД
        cursor.execute('DELETE FROM object_route_sheets WHERE object_id = ?', (object_id,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        # Удаляем физические файлы
        if deleted:
            from flask import current_app
            import os
            route_sheets_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'route_sheets')
            for sheet in sheets:
                filepath = os.path.join(route_sheets_dir, sheet['filename'])
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        logger.error(f"Ошибка при удалении файла {sheet['filename']}: {e}")
            
            logger.info(f"✅ Удалены все маршрутные листы для объекта {object_id}")
        
        return deleted > 0
        
    except Exception as e:
        logger.error(f"Ошибка при удалении всех маршрутных листов: {e}")
        return False


def get_route_sheet_by_id(sheet_id):
    """Получает информацию о маршрутном листе по ID"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, object_id, filename, original_name, file_size, uploaded_at, uploaded_by
            FROM object_route_sheets
            WHERE id = ?
        ''', (sheet_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
        
    except Exception as e:
        logger.error(f"Ошибка при получении маршрутного листа ID {sheet_id}: {e}")
        return None