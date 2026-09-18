# routes/objects_admin.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import current_user
import logging
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

from database import (
    get_objects_settings_extended,
    update_object_settings_full,
    get_object_by_id, 
    create_object_with_vacancy,
    delete_object,
    get_objects_settings,
    get_global_order, 
    save_global_order,
    get_object_passport,
    save_object_passport,
    update_route_sheet,
    get_route_sheet_filename,
    delete_route_sheet,
    log_user_action,
    get_route_sheets,
    add_route_sheet,
    delete_route_sheet_by_id,
    delete_all_route_sheets,
    get_route_sheet_by_id,
    get_help_card,
    save_help_card
)
from config import OBJECTS_BASE

logger = logging.getLogger(__name__)

objects_admin_bp = Blueprint('objects_admin', __name__, url_prefix='/api/admin/objects')

HELP_CARD_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}


@objects_admin_bp.route('', methods=['GET'])
def get_objects():
    """Получение списка всех объектов с настройками"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    objects = get_objects_settings_extended()
    
    return jsonify({
        'objects': objects,
        'base_objects': OBJECTS_BASE
    })


@objects_admin_bp.route('/<int:object_id>', methods=['GET'])
def get_object(object_id):
    """Получение информации об объекте"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    obj = get_object_by_id(object_id)
    if not obj:
        return jsonify({'error': 'Объект не найден'}), 404
    
    return jsonify(obj)


@objects_admin_bp.route('', methods=['POST'])
def create_object_api():
    """Создание нового объекта"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    
    # Валидация обязательных полей
    required_fields = ['name', 'positionName', 'ageMin', 'ageMax', 'allowedGenders', 'allowedNationalities']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Поле {field} обязательно'}), 400
    
    # Валидация числовых полей
    try:
        age_min = int(data['ageMin'])
        age_max = int(data['ageMax'])
        if age_min < 18 or age_min > 100:
            return jsonify({'error': 'Минимальный возраст должен быть от 18 до 100'}), 400
        if age_max < age_min:
            return jsonify({'error': 'Максимальный возраст должен быть больше минимального'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Возраст должен быть числом'}), 400
    
    # Валидация списков
    allowed_genders = data.get('allowedGenders', [])
    if not isinstance(allowed_genders, list) or not allowed_genders:
        return jsonify({'error': 'Укажите допустимые полы'}), 400
    
    allowed_nationalities = data.get('allowedNationalities', [])
    if not isinstance(allowed_nationalities, list) or not allowed_nationalities:
        return jsonify({'error': 'Укажите допустимые гражданства'}), 400

    name = str(data.get('name', '')).strip()
    position_name = str(data.get('positionName', '')).strip()
    if not name:
        return jsonify({'error': 'Название объекта обязательно'}), 400
    if not position_name:
        return jsonify({'error': 'Должность обязательна'}), 400
    
    allows_conviction = bool(data.get('allowsConviction', False))
    strict_labor_code = bool(data.get('strictLaborCode', False))
    link = data.get('link', '')
    visible = bool(data.get('visible', True))
    priority = bool(data.get('priority', False))
    region = data.get('region', '')
    
    object_id = create_object_with_vacancy(
        name=name,
        position_name=position_name,
        age_min=age_min,
        age_max=age_max,
        allowed_genders=allowed_genders,
        allowed_nationalities=allowed_nationalities,
        allows_conviction=allows_conviction,
        link=link,
        visible=visible,
        priority=priority,
        region=region,
        strict_labor_code=strict_labor_code
    )
    
    if object_id == 'duplicate':
        return jsonify({'error': 'Объект с таким именем уже существует'}), 409

    if not object_id:
        return jsonify({'error': 'Ошибка при создании объекта (возможно, такое имя уже существует)'}), 500
    
    log_user_action(
        current_user.id,
        'create_object',
        f"Создан объект {name} с должностью {position_name} (ID: {object_id})",
        request.remote_addr
    )
    
    return jsonify({'success': True, 'object_id': object_id})


@objects_admin_bp.route('/<int:object_id>', methods=['PUT'])
def update_object_api(object_id):
    """Обновление объекта"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    
    # Подготавливаем данные для обновления
    updates = {}
    
    if 'name' in data:
        updates['name'] = data['name']
    
    if 'ageMin' in data:
        try:
            age_min = int(data['ageMin'])
            if age_min < 18 or age_min > 100:
                return jsonify({'error': 'Минимальный возраст должен быть от 18 до 100'}), 400
            updates['age_min'] = age_min
        except (ValueError, TypeError):
            return jsonify({'error': 'Возраст должен быть числом'}), 400
    
    if 'ageMax' in data:
        try:
            age_max = int(data['ageMax'])
            updates['age_max'] = age_max
        except (ValueError, TypeError):
            return jsonify({'error': 'Возраст должен быть числом'}), 400
    
    if 'allowedGenders' in data:
        if not isinstance(data['allowedGenders'], list) or not data['allowedGenders']:
            return jsonify({'error': 'Укажите допустимые полы'}), 400
        updates['allowed_genders'] = data['allowedGenders']
    
    if 'allowedNationalities' in data:
        if not isinstance(data['allowedNationalities'], list) or not data['allowedNationalities']:
            return jsonify({'error': 'Укажите допустимые гражданства'}), 400
        updates['allowed_nationalities'] = data['allowedNationalities']
    
    if 'allowsConviction' in data:
        updates['allows_conviction'] = bool(data['allowsConviction'])

    if 'strictLaborCode' in data:
        updates['strict_labor_code'] = bool(data['strictLaborCode'])
    
    if 'link' in data:
        updates['link'] = data['link']
    
    if 'visible' in data:
        updates['visible'] = bool(data['visible'])
    
    if 'priority' in data:
        updates['priority'] = bool(data['priority'])
    
    if 'region' in data:
        updates['region'] = data['region']
    
    if not updates:
        return jsonify({'error': 'Нет данных для обновления'}), 400
    
    # Проверяем, что возраст min <= max
    age_min = updates.get('age_min')
    age_max = updates.get('age_max')
    if age_min is not None and age_max is not None:
        if age_min > age_max:
            return jsonify({'error': 'Минимальный возраст не может быть больше максимального'}), 400
    
    success = update_object_settings_full(object_id, updates)
    
    if not success:
        return jsonify({'error': 'Ошибка при обновлении объекта'}), 500
    
    log_user_action(current_user.id, 'update_object', f"Обновлён объект ID {object_id}", request.remote_addr)
    
    return jsonify({'success': True})


@objects_admin_bp.route('/<int:object_id>', methods=['DELETE'])
def delete_object_api(object_id):
    """Удаление объекта"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    # Проверяем, существует ли объект
    obj = get_object_by_id(object_id)
    if not obj:
        return jsonify({'error': 'Объект не найден'}), 404
    
    # Не даём удалить объекты из базовой конфигурации (первые 23)
    if object_id <= len(OBJECTS_BASE):
        return jsonify({'error': 'Нельзя удалить базовый объект из конфигурации'}), 400
    
    success = delete_object(object_id)
    
    if not success:
        return jsonify({'error': 'Ошибка при удалении объекта'}), 500
    
    log_user_action(current_user.id, 'delete_object', f"Удалён объект {obj['name']} (ID: {object_id})", request.remote_addr)
    
    return jsonify({'success': True})


@objects_admin_bp.route('/order', methods=['GET'])
def get_order():
    """Получение порядка объектов"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    order = get_global_order()
    return jsonify({'order': order or []})


@objects_admin_bp.route('/order', methods=['POST'])
def save_order():
    """Сохранение порядка объектов"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role not in ['admin']:
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    order = data.get('order', [])
    
    if not isinstance(order, list):
        return jsonify({'error': 'Некорректный формат порядка'}), 400
    
    success = save_global_order(order)
    
    if not success:
        return jsonify({'error': 'Ошибка при сохранении порядка'}), 500
    
    log_user_action(current_user.id, 'save_order', f"Сохранён порядок объектов ({len(order)} объектов)", request.remote_addr)
    
    return jsonify({'success': True})


# ========== ЭНДПОИНТЫ ДЛЯ ПАСПОРТОВ ==========

@objects_admin_bp.route('/<int:object_id>/passport', methods=['GET'])
def get_passport(object_id):
    """Получение паспорта объекта"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем права доступа к объекту
    if current_user.role != 'admin':
        if not current_user.can_view_object(object_id, 'selection'):
            return jsonify({'error': 'Forbidden'}), 403
    
    passport = get_object_passport(object_id)
    return jsonify(passport or {})


@objects_admin_bp.route('/<int:object_id>/passport', methods=['POST'])
def save_passport(object_id):
    """Сохранение паспорта объекта (только админ)"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json()
    success = save_object_passport(object_id, data)
    
    if success:
        log_user_action(current_user.id, 'save_passport', f"Сохранён паспорт объекта ID {object_id}", request.remote_addr)
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Ошибка при сохранении паспорта'}), 500


# ========== ЭНДПОИНТЫ ДЛЯ ШПАРГАЛКИ "ДОКУМЕНТЫ СНГ" ==========

@objects_admin_bp.route('/help-cards/cis-documents', methods=['GET'])
def get_cis_documents_help_card():
    """Получение шпаргалки по документам СНГ."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin' and not current_user.can_view_selection():
        return jsonify({'error': 'Forbidden'}), 403

    card = get_help_card('cis-documents')
    if not card:
        return jsonify({'error': 'Шпаргалка не найдена'}), 404

    return jsonify(card)


@objects_admin_bp.route('/help-cards/cis-documents', methods=['POST'])
def save_cis_documents_help_card():
    """Сохранение шпаргалки по документам СНГ (только админ)."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json() or {}
    success = save_help_card(
        slug='cis-documents',
        title=data.get('title') or 'Документы для СНГ',
        content=data.get('content') or {},
        source_url=data.get('sourceUrl') or '',
        updated_by=current_user.id
    )

    if not success:
        return jsonify({'error': 'Ошибка при сохранении шпаргалки'}), 500

    log_user_action(current_user.id, 'save_help_card', 'Сохранена шпаргалка Документы СНГ', request.remote_addr)
    return jsonify({'success': True})


@objects_admin_bp.route('/help-cards/cis-documents/images', methods=['POST'])
def upload_cis_documents_help_image():
    """Загрузка картинки для шпаргалки по документам СНГ."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403

    if 'image' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in HELP_CARD_IMAGE_EXTENSIONS:
        return jsonify({'error': 'Можно загружать только картинки: JPG, PNG, WEBP, GIF'}), 400

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    max_size = 10 * 1024 * 1024
    if file_size > max_size:
        return jsonify({'error': 'Картинка слишком большая. Максимум 10 MB'}), 400

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'help_cards')
    os.makedirs(upload_dir, exist_ok=True)

    safe_original = secure_filename(file.filename) or f'image.{ext}'
    if '.' not in safe_original:
        safe_original = f'{safe_original}.{ext}'
    filename = f"cis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{safe_original}"
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    url = f'/static/uploads/help_cards/{filename}'
    log_user_action(current_user.id, 'upload_help_card_image', f'Загружена картинка для Документы СНГ: {safe_original}', request.remote_addr)
    return jsonify({'success': True, 'url': url})


# ========== СТАРЫЕ ЭНДПОИНТЫ ДЛЯ ОДНОГО МАРШРУТНОГО ЛИСТА (ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ) ==========

@objects_admin_bp.route('/<int:object_id>/route-sheet', methods=['POST'])
def upload_route_sheet(object_id):
    """Загрузка маршрутного листа (только админ) - устаревший, используйте /route-sheets"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    if 'route_sheet' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    file = request.files['route_sheet']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    # Проверяем расширение
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Можно загружать только PDF файлы'}), 400
    
    # Проверяем размер файла (30 MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = 30 * 1024 * 1024  # 30 MB
    if file_size > max_size:
        return jsonify({'error': f'Файл слишком большой. Максимум 30 MB'}), 400
    
    # Проверяем количество уже загруженных файлов
    existing_sheets = get_route_sheets(object_id)
    if len(existing_sheets) >= 5:
        return jsonify({'error': 'Максимум 5 маршрутных листов на объект'}), 400
    
    # Создаём директорию для маршрутных листов
    from flask import current_app
    route_sheets_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'route_sheets')
    os.makedirs(route_sheets_dir, exist_ok=True)
    
    # Генерируем уникальное имя файла
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_original = file.filename.replace(' ', '_')
    filename = f"route_sheet_{object_id}_{timestamp}_{safe_original}"
    filepath = os.path.join(route_sheets_dir, filename)
    
    file.save(filepath)
    
    # Сохраняем оригинальное название
    original_name = file.filename
    
    # Добавляем запись в БД
    sheet_id = add_route_sheet(
        object_id=object_id,
        filename=filename,
        original_name=original_name,
        file_size=file_size,
        uploaded_by=current_user.id
    )
    
    if not sheet_id:
        # Если не удалось добавить в БД, удаляем файл
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Ошибка при сохранении в БД'}), 500
    
    # Для обратной совместимости сохраняем также в старую таблицу
    update_route_sheet(object_id, filename)
    
    log_user_action(
        current_user.id, 
        'upload_route_sheet', 
        f"Загружен маршрутный лист для объекта ID {object_id}: {original_name}", 
        request.remote_addr
    )
    
    return jsonify({
        'success': True, 
        'sheet_id': sheet_id,
        'filename': filename,
        'original_name': original_name
    })


@objects_admin_bp.route('/<int:object_id>/route-sheet', methods=['DELETE'])
def delete_route_sheet_file(object_id):
    """Удаление маршрутного листа (только админ) - устаревший, используйте /route-sheets/{id}"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    # Удаляем все маршрутные листы для обратной совместимости
    success = delete_all_route_sheets(object_id)
    
    if success:
        log_user_action(current_user.id, 'delete_route_sheet', f"Удалены все маршрутные листы для объекта ID {object_id}", request.remote_addr)
    
    return jsonify({'success': True})


@objects_admin_bp.route('/<int:object_id>/route-sheet/download', methods=['GET'])
def download_route_sheet(object_id):
    """Скачивание маршрутного листа - устаревший, используйте /route-sheets/{id}/download"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем права доступа к объекту
    if current_user.role != 'admin':
        if not current_user.can_view_object(object_id, 'selection'):
            return jsonify({'error': 'Forbidden'}), 403
    
    from flask import current_app
    
    # Получаем список маршрутных листов
    sheets = get_route_sheets(object_id)
    if not sheets:
        return jsonify({'error': 'Маршрутные листы не найдены'}), 404
    
    # Скачиваем первый файл (для обратной совместимости)
    sheet = sheets[0]
    filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'route_sheets', sheet['filename'])
    if not os.path.exists(filepath):
        return jsonify({'error': 'Файл не найден'}), 404
    
    return send_file(filepath, as_attachment=True, download_name=sheet['original_name'])


# ========== НОВЫЕ ЭНДПОИНТЫ ДЛЯ МНОЖЕСТВЕННЫХ МАРШРУТНЫХ ЛИСТОВ ==========

@objects_admin_bp.route('/<int:object_id>/route-sheets', methods=['GET'])
def get_route_sheets_api(object_id):
    """Получение списка всех маршрутных листов объекта"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Проверяем права доступа к объекту
    if current_user.role != 'admin':
        if not current_user.can_view_object(object_id, 'selection'):
            return jsonify({'error': 'Forbidden'}), 403
    
    sheets = get_route_sheets(object_id)
    return jsonify(sheets)


@objects_admin_bp.route('/<int:object_id>/route-sheets', methods=['POST'])
def upload_route_sheet_api(object_id):
    """
    Загрузка нового маршрутного листа (максимум 5 файлов)
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    if 'route_sheet' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    file = request.files['route_sheet']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    # Проверяем расширение
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Можно загружать только PDF файлы'}), 400
    
    # Проверяем размер файла (30 MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = 30 * 1024 * 1024  # 30 MB
    if file_size > max_size:
        return jsonify({'error': f'Файл слишком большой. Максимум 30 MB'}), 400
    
    # Проверяем количество уже загруженных файлов
    existing_sheets = get_route_sheets(object_id)
    if len(existing_sheets) >= 5:
        return jsonify({'error': 'Максимум 5 маршрутных листов на объект'}), 400
    
    # Создаём директорию для маршрутных листов
    from flask import current_app
    route_sheets_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'route_sheets')
    os.makedirs(route_sheets_dir, exist_ok=True)
    
    # Генерируем уникальное имя файла
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_original = file.filename.replace(' ', '_')
    filename = f"route_sheet_{object_id}_{timestamp}_{safe_original}"
    filepath = os.path.join(route_sheets_dir, filename)
    
    file.save(filepath)
    
    # Сохраняем оригинальное название
    original_name = file.filename
    
    # Добавляем запись в БД
    sheet_id = add_route_sheet(
        object_id=object_id,
        filename=filename,
        original_name=original_name,
        file_size=file_size,
        uploaded_by=current_user.id
    )
    
    if not sheet_id:
        # Если не удалось добавить в БД, удаляем файл
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Ошибка при сохранении в БД'}), 500
    
    # Для обратной совместимости сохраняем также в старую таблицу (первый файл)
    update_route_sheet(object_id, filename)
    
    log_user_action(
        current_user.id, 
        'upload_route_sheet', 
        f"Загружен маршрутный лист для объекта ID {object_id}: {original_name}", 
        request.remote_addr
    )
    
    return jsonify({
        'success': True, 
        'sheet_id': sheet_id,
        'filename': filename,
        'original_name': original_name
    })


@objects_admin_bp.route('/route-sheets/<int:sheet_id>', methods=['DELETE'])
def delete_route_sheet_by_id_api(sheet_id):
    """Удаление конкретного маршрутного листа по ID"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    # Получаем информацию о листе
    sheet = get_route_sheet_by_id(sheet_id)
    if not sheet:
        return jsonify({'error': 'Маршрутный лист не найден'}), 404
    
    object_id = sheet['object_id']
    original_name = sheet['original_name']
    
    success = delete_route_sheet_by_id(sheet_id)
    
    if success:
        log_user_action(
            current_user.id, 
            'delete_route_sheet', 
            f"Удалён маршрутный лист для объекта ID {object_id}: {original_name}", 
            request.remote_addr
        )
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Ошибка при удалении'}), 500


@objects_admin_bp.route('/<int:object_id>/route-sheets/all', methods=['DELETE'])
def delete_all_route_sheets_api(object_id):
    """Удаление всех маршрутных листов объекта"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    success = delete_all_route_sheets(object_id)
    
    if success:
        log_user_action(
            current_user.id, 
            'delete_all_route_sheets', 
            f"Удалены все маршрутные листы для объекта ID {object_id}", 
            request.remote_addr
        )
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Ошибка при удалении'}), 500


@objects_admin_bp.route('/route-sheets/<int:sheet_id>/download', methods=['GET'])
def download_route_sheet_by_id(sheet_id):
    """Скачивание конкретного маршрутного листа по ID"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    sheet = get_route_sheet_by_id(sheet_id)
    if not sheet:
        return jsonify({'error': 'Маршрутный лист не найден'}), 404
    
    object_id = sheet['object_id']
    
    # Проверяем права доступа к объекту
    if current_user.role != 'admin':
        if not current_user.can_view_object(object_id, 'selection'):
            return jsonify({'error': 'Forbidden'}), 403
    
    from flask import current_app
    filepath = os.path.join(current_app.root_path, 'static', 'uploads', 'route_sheets', sheet['filename'])
    if not os.path.exists(filepath):
        return jsonify({'error': 'Файл не найден'}), 404
    
    # Используем оригинальное имя для скачивания
    download_name = sheet['original_name']
    return send_file(filepath, as_attachment=True, download_name=download_name)
