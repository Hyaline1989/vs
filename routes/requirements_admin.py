# routes/requirements_admin.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import logging
import sqlite3
import urllib.parse
from database import (
    get_all_vacancy_data,
    save_vacancy_object,
    delete_vacancy_object,
    save_vacancy_position,
    delete_vacancy_position,
    save_vacancy_requirements_batch,
    init_vacancy_tables,
    get_current_requirements,
    save_current_requirements,
    DB_NAME
)

logger = logging.getLogger(__name__)

requirements_admin_bp = Blueprint('requirements_admin', __name__, url_prefix='/api/requirements')

# Инициализируем таблицы при загрузке модуля
init_vacancy_tables()


@requirements_admin_bp.route('/vacancy', methods=['GET'])
@login_required
def get_vacancy():
    """Получение ТЕКУЩИХ потребностей (без даты)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role not in ['admin', 'manager']:
        if not current_user.can_view_selection():
            return jsonify({'error': 'Forbidden'}), 403
    
    try:
        data = get_current_requirements()
        
        # Если current_requirements пустая, но есть vacancy_objects - создаём базовые записи
        if not data or len(data) == 0:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            # Получаем все объекты и их должности
            cursor.execute('''
                SELECT vo.name, vp.name 
                FROM vacancy_objects vo
                JOIN vacancy_positions vp ON vp.object_id = vo.id
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                # Создаём структуру для current_requirements
                new_data = {}
                for obj_name, pos_name in rows:
                    if obj_name not in new_data:
                        new_data[obj_name] = {
                            'rf': {'men': 0, 'women': 0, 'family': 0},
                            'cis': {'men': 0, 'women': 0, 'family': 0},
                            'positions': [],
                            'is_high': False
                        }
                    
                    # Добавляем должность, если её нет
                    existing_positions = [p['name'] for p in new_data[obj_name]['positions']]
                    if pos_name not in existing_positions:
                        new_data[obj_name]['positions'].append({
                            'name': pos_name,
                            'rf': {'men': 0, 'women': 0, 'family': 0},
                            'cis': {'men': 0, 'women': 0, 'family': 0}
                        })
                
                # Сохраняем в current_requirements
                if new_data:
                    save_current_requirements(new_data)
                    data = new_data
                    logger.info(f"✅ Автоматически созданы записи в current_requirements для {len(new_data)} объектов")
        
        return jsonify({
            'date': 'current',
            'data': data if data else {}
        })
    except Exception as e:
        logger.error(f"Ошибка в get_vacancy: {e}")
        return jsonify({'date': 'current', 'data': {}})


@requirements_admin_bp.route('/object', methods=['POST'])
@login_required
def create_object():
    """Создание нового объекта вакансии (только админ)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может создавать объекты'}), 403
    
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'error': 'Название объекта обязательно'}), 400
    
    # Проверяем, существует ли уже такой объект
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM vacancy_objects WHERE name = ?', (name,))
    existing = cursor.fetchone()
    conn.close()
    
    if existing:
        return jsonify({'error': f'Объект "{name}" уже существует'}), 400
    
    # Создаём объект
    obj_id = save_vacancy_object(name)
    
    if not obj_id:
        return jsonify({'error': 'Ошибка при создании объекта'}), 500
    
    # Добавляем должность по умолчанию
    default_position = "Основная потребность"
    pos_id = save_vacancy_position(name, default_position)
    
    # Добавляем объект в current_requirements
    try:
        current_data = get_current_requirements()
        if name not in current_data:
            current_data[name] = {
                'rf': {'men': 0, 'women': 0, 'family': 0},
                'cis': {'men': 0, 'women': 0, 'family': 0},
                'positions': [{
                    'name': default_position,
                    'rf': {'men': 0, 'women': 0, 'family': 0},
                    'cis': {'men': 0, 'women': 0, 'family': 0}
                }],
                'is_high': False
            }
            save_current_requirements(current_data)
            logger.info(f"✅ Объект {name} добавлен в current_requirements")
    except Exception as e:
        logger.error(f"Ошибка при добавлении объекта в current_requirements: {e}")
    
    from database import log_user_action
    log_user_action(current_user.id, 'create_vacancy_object', f"Создан объект вакансии: {name}", request.remote_addr)
    
    return jsonify({'success': True, 'id': obj_id, 'message': f'Объект "{name}" создан'})


@requirements_admin_bp.route('/object/<string:name>', methods=['DELETE'])
@login_required
def delete_object(name):
    """Удаление объекта вакансии (только админ)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может удалять объекты'}), 403
    
    # Декодируем название (если было закодировано)
    decoded_name = urllib.parse.unquote(name)
    
    logger.info(f"Попытка удаления объекта: '{decoded_name}'")
    
    # Удаляем из current_requirements (всегда, даже если нет в vacancy_objects)
    deleted_from_current = False
    try:
        current_data = get_current_requirements()
        if decoded_name in current_data:
            del current_data[decoded_name]
            save_current_requirements(current_data)
            deleted_from_current = True
            logger.info(f"✅ Объект {decoded_name} удалён из current_requirements")
    except Exception as e:
        logger.error(f"Ошибка при удалении объекта из current_requirements: {e}")
    
    # Проверяем, существует ли объект в vacancy_objects
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM vacancy_objects WHERE name = ?', (decoded_name,))
    existing = cursor.fetchone()
    conn.close()
    
    if existing:
        # Удаляем из vacancy_objects (каскадно удалит и vacancy_positions, и vacancy_requirements)
        if delete_vacancy_object(decoded_name):
            from database import log_user_action
            log_user_action(current_user.id, 'delete_vacancy_object', f"Удалён объект вакансии: {decoded_name}", request.remote_addr)
            return jsonify({'success': True, 'message': f'Объект "{decoded_name}" удалён из всех таблиц'})
        else:
            if deleted_from_current:
                return jsonify({'success': True, 'message': f'Объект "{decoded_name}" удалён только из current_requirements'})
            else:
                return jsonify({'error': 'Ошибка при удалении объекта'}), 500
    else:
        # Объекта нет в vacancy_objects, но могли удалить из current_requirements
        if deleted_from_current:
            return jsonify({'success': True, 'message': f'Объект "{decoded_name}" удалён из current_requirements'})
        else:
            logger.warning(f"Объект '{decoded_name}' не найден ни в одной таблице")
            return jsonify({'error': f'Объект "{decoded_name}" не найден'}), 404


@requirements_admin_bp.route('/position', methods=['POST'])
@login_required
def create_position():
    """Добавление должности к объекту (только админ)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может добавлять должности'}), 403
    
    data = request.get_json()
    object_name = data.get('object_name', '').strip()
    position_name = data.get('position_name', '').strip()
    
    if not object_name or not position_name:
        return jsonify({'error': 'Название объекта и должности обязательны'}), 400
    
    pos_id = save_vacancy_position(object_name, position_name)
    
    if pos_id:
        # Также добавляем должность в current_requirements
        try:
            current_data = get_current_requirements()
            if object_name not in current_data:
                current_data[object_name] = {
                    'rf': {'men': 0, 'women': 0, 'family': 0},
                    'cis': {'men': 0, 'women': 0, 'family': 0},
                    'positions': [],
                    'is_high': False
                }
            
            # Проверяем, нет ли уже такой должности
            existing = False
            for pos in current_data[object_name]['positions']:
                if pos['name'] == position_name:
                    existing = True
                    break
            
            if not existing:
                current_data[object_name]['positions'].append({
                    'name': position_name,
                    'rf': {'men': 0, 'women': 0, 'family': 0},
                    'cis': {'men': 0, 'women': 0, 'family': 0}
                })
                save_current_requirements(current_data)
        except Exception as e:
            logger.error(f"Ошибка при добавлении должности в current_requirements: {e}")
        
        from database import log_user_action
        log_user_action(current_user.id, 'create_vacancy_position', 
                       f"Добавлена должность {position_name} к объекту {object_name}", 
                       request.remote_addr)
        return jsonify({'success': True, 'id': pos_id})
    else:
        return jsonify({'error': 'Ошибка создания или должность уже существует'}), 400


@requirements_admin_bp.route('/position', methods=['DELETE'])
@login_required
def delete_position():
    """Удаление должности (только админ)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может удалять должности'}), 403
    
    data = request.get_json()
    object_name = data.get('object_name', '').strip()
    position_name = data.get('position_name', '').strip()
    
    if not object_name or not position_name:
        return jsonify({'error': 'Название объекта и должности обязательны'}), 400
    
    if delete_vacancy_position(object_name, position_name):
        # Также удаляем должность из current_requirements
        try:
            current_data = get_current_requirements()
            if object_name in current_data:
                current_data[object_name]['positions'] = [
                    p for p in current_data[object_name]['positions'] 
                    if p['name'] != position_name
                ]
                save_current_requirements(current_data)
        except Exception as e:
            logger.error(f"Ошибка при удалении должности из current_requirements: {e}")
        
        from database import log_user_action
        log_user_action(current_user.id, 'delete_vacancy_position', 
                       f"Удалена должность {position_name} из объекта {object_name}", 
                       request.remote_addr)
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Должность не найдена'}), 404


@requirements_admin_bp.route('/save-all', methods=['POST'])
@login_required
def save_all_requirements():
    """Сохранение ТЕКУЩИХ потребностей с сохранением МАКСИМАЛЬНОЙ потребности для дашборда"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может редактировать потребности'}), 403
    
    data = request.get_json()
    objects_data = data.get('objects', {})
    
    # Сохраняем в current_requirements (для подбора объектов)
    if save_current_requirements(objects_data):
        # Синхронизируем с vacancy_requirements для дашборда с сохранением МАКСИМУМА
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        for obj_name, obj_data in objects_data.items():
            is_high = obj_data.get('is_high', False)
            
            for pos in obj_data.get('positions', []):
                pos_name = pos.get('name', '')
                if not pos_name:
                    continue
                
                # Получаем position_id
                cursor.execute('''
                    SELECT vp.id FROM vacancy_positions vp
                    JOIN vacancy_objects vo ON vo.id = vp.object_id
                    WHERE vo.name = ? AND vp.name = ?
                ''', (obj_name, pos_name))
                pos_row = cursor.fetchone()
                
                if pos_row:
                    pos_id = pos_row[0]
                    new_men = pos.get('rf', {}).get('men', 0)
                    new_women = pos.get('rf', {}).get('women', 0)
                    new_family = pos.get('rf', {}).get('family', 0)
                    new_cis_men = pos.get('cis', {}).get('men', 0)
                    new_cis_women = pos.get('cis', {}).get('women', 0)
                    new_cis_family = pos.get('cis', {}).get('family', 0)
                    
                    # Получаем текущие значения за сегодня (если есть)
                    cursor.execute('''
                        SELECT rf_men, rf_women, rf_family, cis_men, cis_women, cis_family, is_high
                        FROM vacancy_requirements
                        WHERE position_id = ? AND date = ?
                    ''', (pos_id, today))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Сохраняем МАКСИМАЛЬНОЕ значение
                        final_men = max(existing[0], new_men)
                        final_women = max(existing[1], new_women)
                        final_family = max(existing[2], new_family)
                        final_cis_men = max(existing[3], new_cis_men)
                        final_cis_women = max(existing[4], new_cis_women)
                        final_cis_family = max(existing[5], new_cis_family)
                        final_is_high = existing[6] or is_high
                        
                        cursor.execute('''
                            UPDATE vacancy_requirements 
                            SET rf_men = ?, rf_women = ?, rf_family = ?,
                                cis_men = ?, cis_women = ?, cis_family = ?,
                                is_high = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE position_id = ? AND date = ?
                        ''', (final_men, final_women, final_family,
                              final_cis_men, final_cis_women, final_cis_family,
                              1 if final_is_high else 0,
                              pos_id, today))
                    else:
                        # Вставляем новую запись
                        cursor.execute('''
                            INSERT INTO vacancy_requirements 
                            (position_id, date, rf_men, rf_women, rf_family, cis_men, cis_women, cis_family, is_high)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (pos_id, today,
                              new_men, new_women, new_family,
                              new_cis_men, new_cis_women, new_cis_family,
                              1 if is_high else 0))
            
            logger.info(f"✅ Синхронизирован объект {obj_name} для дашборда на {today} (сохранён максимум)")
        
        conn.commit()
        conn.close()
        
        from database import log_user_action
        log_user_action(current_user.id, 'save_current_requirements', 
                       f"Сохранены текущие потребности для {len(objects_data)} объектов (максимумы сохранены)", 
                       request.remote_addr)
        return jsonify({'success': True, 'message': f'Сохранено {len(objects_data)} объектов'})
    else:
        return jsonify({'error': 'Ошибка при сохранении потребностей'}), 500