# database/vacancy.py
# -*- coding: utf-8 -*-
import sqlite3
import logging
from datetime import datetime

from database.db_core import DB_NAME

logger = logging.getLogger(__name__)


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