# routes/requirements_admin.py - ФИНАЛЬНАЯ ВЕРСИЯ С КНОПКОЙ ОБНУЛЕНИЯ
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
    DB_NAME,
    is_system_admin,
    log_user_action
)

logger = logging.getLogger(__name__)

requirements_admin_bp = Blueprint('requirements_admin', __name__, url_prefix='/api/requirements')

# Инициализируем таблицы при загрузке модуля
init_vacancy_tables()


@requirements_admin_bp.route('/vacancy', methods=['GET'])
@login_required
def get_vacancy():
    """Получение ТЕКУЩИХ потребностей (без даты) - БЕЗ АВТОСОЗДАНИЯ"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role not in ['admin', 'manager']:
        if not current_user.can_view_selection():
            return jsonify({'error': 'Forbidden'}), 403
    
    try:
        # Просто возвращаем то, что есть в current_requirements
        data = get_current_requirements()
        
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
    
    # Проверяем, существует ли уже такой объект в vacancy_objects
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM vacancy_objects WHERE name = ?', (name,))
    existing = cursor.fetchone()
    conn.close()
    
    if existing:
        return jsonify({'error': f'Объект "{name}" уже существует'}), 400
    
    # Создаём объект в vacancy_objects
    obj_id = save_vacancy_object(name)
    
    if not obj_id:
        return jsonify({'error': 'Ошибка при создании объекта'}), 500
    
    # Добавляем должность по умолчанию
    default_position = "Основная потребность"
    save_vacancy_position(name, default_position)
    
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
    
    log_user_action(current_user.id, 'create_vacancy_object', f"Создан объект вакансии: {name}", request.remote_addr)
    
    return jsonify({'success': True, 'id': obj_id, 'message': f'Объект "{name}" создан'})


@requirements_admin_bp.route('/object/<string:name>', methods=['DELETE'])
@login_required
def delete_object(name):
    """Удаление объекта вакансии (только админ) - удаляет из обеих таблиц"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может удалять объекты'}), 403
    
    # Декодируем название
    decoded_name = urllib.parse.unquote(name)
    
    logger.info(f"Попытка удаления объекта: '{decoded_name}'")
    
    deleted_from_current = False
    deleted_from_vacancy = False
    
    # 1. Удаляем из current_requirements
    try:
        current_data = get_current_requirements()
        if decoded_name in current_data:
            del current_data[decoded_name]
            save_current_requirements(current_data)
            deleted_from_current = True
            logger.info(f"✅ Объект {decoded_name} удалён из current_requirements")
    except Exception as e:
        logger.error(f"Ошибка при удалении из current_requirements: {e}")
    
    # 2. Удаляем из vacancy_objects (каскадно удалит всё связанное)
    try:
        if delete_vacancy_object(decoded_name):
            deleted_from_vacancy = True
            logger.info(f"✅ Объект {decoded_name} удалён из vacancy_objects")
    except Exception as e:
        logger.error(f"Ошибка при удалении из vacancy_objects: {e}")
    
    # 3. Результат
    if deleted_from_current or deleted_from_vacancy:
        log_user_action(current_user.id, 'delete_vacancy_object', 
                       f"Удалён объект: {decoded_name} (current:{deleted_from_current}, vacancy:{deleted_from_vacancy})", 
                       request.remote_addr)
        return jsonify({'success': True, 'message': f'Объект "{decoded_name}" удалён'})
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
        
        log_user_action(current_user.id, 'delete_vacancy_position', 
                       f"Удалена должность {position_name} из объекта {object_name}", 
                       request.remote_addr)
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Должность не найдена'}), 404


@requirements_admin_bp.route('/save-all', methods=['POST'])
@login_required
def save_all_requirements():
    """
    Сохранение ТЕКУЩИХ потребностей.
    
    Что делает:
    1. Сохраняет данные в current_requirements (для Подбора объектов)
    2. Синхронизирует ЦИФРЫ потребности с vacancy_requirements (для Дашборда)
    3. НЕ синхронизирует приоритеты (is_high) — они фиксируются только через кнопку "Зафиксировать день"
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может редактировать потребности'}), 403
    
    data = request.get_json()
    objects_data = data.get('objects', {})
    
    # 1. Сохраняем в current_requirements (для подбора объектов)
    if not save_current_requirements(objects_data):
        return jsonify({'error': 'Ошибка при сохранении потребностей'}), 500
    
    # 2. Синхронизируем с vacancy_requirements для дашборда
    #    НО синхронизируем ТОЛЬКО цифры, НЕ синхронизируем is_high
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        for obj_name, obj_data in objects_data.items():
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
                        # Сохраняем МАКСИМАЛЬНОЕ значение для ЦИФР
                        final_men = max(existing[0], new_men)
                        final_women = max(existing[1], new_women)
                        final_family = max(existing[2], new_family)
                        final_cis_men = max(existing[3], new_cis_men)
                        final_cis_women = max(existing[4], new_cis_women)
                        final_cis_family = max(existing[5], new_cis_family)
                        
                        # ВАЖНО: is_high НЕ МЕНЯЕМ! Оставляем существующее значение.
                        # Приоритет фиксируется только через кнопку "Зафиксировать день"
                        final_is_high = existing[6]  # БЕРЁМ СУЩЕСТВУЮЩЕЕ, НЕ МЕНЯЕМ!
                        
                        cursor.execute('''
                            UPDATE vacancy_requirements 
                            SET rf_men = ?, rf_women = ?, rf_family = ?,
                                cis_men = ?, cis_women = ?, cis_family = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE position_id = ? AND date = ?
                        ''', (final_men, final_women, final_family,
                              final_cis_men, final_cis_women, final_cis_family,
                              pos_id, today))
                    else:
                        # Вставляем новую запись
                        # is_high ставим False по умолчанию (приоритет будет установлен позже через кнопку)
                        cursor.execute('''
                            INSERT INTO vacancy_requirements 
                            (position_id, date, rf_men, rf_women, rf_family, cis_men, cis_women, cis_family, is_high)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (pos_id, today,
                              new_men, new_women, new_family,
                              new_cis_men, new_cis_women, new_cis_family,
                              0))  # is_high = 0 (не приоритетный)
            
            logger.info(f"✅ Синхронизированы ЦИФРЫ потребности для дашборда на {today} (приоритеты НЕ затронуты)")
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Ошибка при синхронизации с vacancy_requirements: {e}")
        return jsonify({'error': f'Ошибка синхронизации: {str(e)}'}), 500
    finally:
        conn.close()
    
    log_user_action(current_user.id, 'save_current_requirements', 
                   f"Сохранены текущие потребности для {len(objects_data)} объектов (цифры синхронизированы, приоритеты НЕ затронуты)", 
                   request.remote_addr)
    
    return jsonify({'success': True, 'message': f'Сохранено {len(objects_data)} объектов'})


# ========== НОВЫЙ ЭНДПОИНТ: ОБНУЛЕНИЕ ПОТРЕБНОСТИ ОБЪЕКТА ==========

@requirements_admin_bp.route('/reset-object', methods=['POST'])
@login_required
def reset_object_requirements():
    """
    Сбрасывает максимальную потребность объекта в БД (только для системного администратора)
    Кнопка ⭕️ "Обнулить потребность в БД" — страховка от случайных ошибок
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Только системный администратор (id=1)
    if not is_system_admin(current_user.id):
        return jsonify({'error': 'Только системный администратор может обнулять потребности'}), 403
    
    data = request.get_json()
    object_name = data.get('object_name', '').strip()
    
    if not object_name:
        return jsonify({'error': 'Не указан объект'}), 400
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # 1. Находим все position_id для этого объекта в vacancy_positions
        cursor.execute('''
            SELECT vp.id FROM vacancy_positions vp
            JOIN vacancy_objects vo ON vo.id = vp.object_id
            WHERE vo.name = ?
        ''', (object_name,))
        
        position_ids = [row[0] for row in cursor.fetchall()]
        
        if not position_ids:
            conn.close()
            return jsonify({'error': f'Объект "{object_name}" не найден в vacancy_objects'}), 404
        
        # 2. Обновляем записи за сегодня: обнуляем ВСЕ числа (rf_*, cis_*)
        placeholders = ','.join(['?'] * len(position_ids))
        cursor.execute(f'''
            UPDATE vacancy_requirements 
            SET rf_men = 0, rf_women = 0, rf_family = 0,
                cis_men = 0, cis_women = 0, cis_family = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE position_id IN ({placeholders}) AND date = ?
        ''', position_ids + [today])
        
        updated_count = cursor.rowcount
        logger.info(f"Обнулено {updated_count} записей в vacancy_requirements для объекта {object_name} за {today}")
        
        # 3. Также обнуляем в current_requirements для этого объекта
        cursor.execute('''
            UPDATE current_requirements 
            SET rf_men = 0, rf_women = 0, rf_family = 0,
                cis_men = 0, cis_women = 0, cis_family = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE object_name = ?
        ''', (object_name,))
        
        current_updated = cursor.rowcount
        logger.info(f"Обнулено {current_updated} записей в current_requirements для объекта {object_name}")
        
        conn.commit()
        conn.close()
        
        log_user_action(
            current_user.id,
            'reset_object_requirements',
            f"Обнулены потребности для объекта {object_name} (vacancy: {updated_count} записей, current: {current_updated} записей)",
            request.remote_addr
        )
        
        return jsonify({
            'success': True,
            'message': f'Потребности объекта "{object_name}" обнулены',
            'updated_count': updated_count,
            'current_updated': current_updated
        })
        
    except Exception as e:
        logger.error(f"Ошибка при обнулении потребностей объекта {object_name}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500