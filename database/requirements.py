# database/requirements.py
# -*- coding: utf-8 -*-
import sqlite3
import logging

from database.db_core import DB_NAME

logger = logging.getLogger(__name__)


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