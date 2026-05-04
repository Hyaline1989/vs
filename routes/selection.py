# routes/selection.py - полная версия
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify, send_file
from flask_login import current_user, login_required
import logging
import sqlite3
import os
import uuid
from werkzeug.utils import secure_filename

from database import (
    get_objects_settings, update_object_settings, get_global_order, save_global_order,
    get_user_module_permissions, get_user_object_permissions, get_objects_settings_extended,
    get_current_requirements, DB_NAME
)
from datetime import datetime

logger = logging.getLogger(__name__)

selection_bp = Blueprint('selection', __name__, url_prefix='/api/selection')

google_api = None

# Настройки для загрузки файлов (временная папка, файлы не сохраняются)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'uploads', 'temp')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'}

# Создаём папку для временных файлов, если её нет
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def init_selection_apis(google):
    global google_api
    google_api = google


@selection_bp.route('/settings')
@login_required
def selection_settings():
    """Получение настроек для подбора объектов (с текущими потребностями)"""
    try:
        for_permissions = request.args.get('for_permissions') == 'true'
        
        if for_permissions:
            if current_user.role not in ['admin', 'manager']:
                return jsonify({'error': 'Forbidden'}), 403
        else:
            if not current_user.can_view_selection():
                return jsonify({'error': 'Forbidden', 'message': 'У вас нет доступа к подбору объектов'}), 403
        
        db_objects = get_objects_settings_extended()
        db_objects = [obj for obj in db_objects if obj.get('visible', True)]
        
        objects_settings = get_objects_settings()
        global_order = get_global_order()
        
        if not global_order:
            global_order = [obj['id'] for obj in db_objects]
            save_global_order(global_order)
        
        current_req = get_current_requirements()
        
        objects = []
        for db_obj in db_objects:
            setting = next((s for s in objects_settings if s['id'] == db_obj['id']), None)
            
            req_data = current_req.get(db_obj['name'], {})
            total_count = (req_data.get('rf', {}).get('men', 0) + 
                          req_data.get('rf', {}).get('women', 0) + 
                          req_data.get('rf', {}).get('family', 0) +
                          req_data.get('cis', {}).get('men', 0) + 
                          req_data.get('cis', {}).get('women', 0) + 
                          req_data.get('cis', {}).get('family', 0))
            
            priority_from_req = req_data.get('is_high', False)
            
            objects.append({
                'id': db_obj['id'],
                'name': db_obj['name'],
                'ageMin': db_obj.get('ageMin', 18),
                'ageMax': db_obj.get('ageMax', 55),
                'allowedGenders': db_obj.get('allowedGenders', ['мужчина', 'женщина']),
                'allowedNationalities': db_obj.get('allowedNationalities', ['РФ']),
                'allowsConviction': db_obj.get('allowsConviction', False),
                'link': db_obj.get('link', ''),
                'visible': setting['visible'] if setting else True,
                'priority': priority_from_req,
                'requirement': total_count
            })
        
        if not for_permissions and current_user.role != 'admin':
            object_perms = get_user_object_permissions(current_user.id)
            visible_object_ids = [obj_id for obj_id, perms in object_perms.items() if perms.get('selection', False)]
            objects = [obj for obj in objects if obj['id'] in visible_object_ids]
        
        return jsonify({
            'objects': objects,
            'globalOrder': global_order,
            'vacancyData': current_req
        })
    except Exception as e:
        logger.error(f"Ошибка загрузки настроек подбора: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@selection_bp.route('/order', methods=['POST'])
@login_required
def selection_order():
    """Сохранение порядка объектов"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    
    module_perms = get_user_module_permissions(current_user.id)
    if not module_perms.get('selection', False):
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        data = request.get_json()
        order = data.get('order', [])
        
        if order:
            save_global_order(order)
            return jsonify({'success': True})
        return jsonify({'error': 'Некорректный порядок'}), 400
    except Exception as e:
        logger.error(f"Ошибка сохранения порядка: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@selection_bp.route('/debug/priority')
@login_required
def debug_priority():
    """Диагностический эндпоинт для проверки приоритетов"""
    if not current_user.is_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT vr.date, vo.name, vr.is_high
            FROM vacancy_requirements vr
            JOIN vacancy_positions vp ON vp.id = vr.position_id
            JOIN vacancy_objects vo ON vo.id = vp.object_id
            WHERE vr.is_high = 1
            ORDER BY vr.date DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        priority_dates = {}
        for row in rows:
            date = row[0]
            name = row[1]
            if date not in priority_dates:
                priority_dates[date] = []
            priority_dates[date].append(name)
        
        return jsonify({
            'priority_by_date': priority_dates
        })
    except Exception as e:
        logger.error(f"Ошибка диагностики приоритетов: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ========== НАПРАВЛЕНИЕ СОТРУДНИКА (СОЗДАНИЕ ЛИДА С ФАЙЛАМИ) ==========

@selection_bp.route('/create-deal', methods=['POST'])
@login_required
def create_direction_deal():
    """Создание лида в Bitrix24 с прикреплением всех файлов"""
    if not current_user.can_view_selection():
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        # Получаем данные из формы
        object_id = request.form.get('object_id')
        object_name = request.form.get('object_name')
        position_name = request.form.get('position_name', '')
        candidate_name = request.form.get('candidate_name', '').strip()
        candidate_phone = request.form.get('candidate_phone', '').strip()
        agent_name = request.form.get('agent_name', '').strip()
        agent_object = request.form.get('agent_object', '').strip()
        
        # Валидация
        if not object_name:
            return jsonify({'error': 'Не указан объект'}), 400
        
        if not candidate_name:
            return jsonify({'error': 'Введите ФИО кандидата'}), 400
        
        if not candidate_phone:
            return jsonify({'error': 'Введите номер телефона'}), 400
        
        if not agent_name:
            return jsonify({'error': 'Введите ФИО агента'}), 400
        
        if not agent_object:
            return jsonify({'error': 'Введите объект'}), 400
        
        # Получаем ВСЕ файлы
        files = request.files.getlist('attachments')
        valid_files = [f for f in files if f and f.filename]
        
        # Получаем информацию о пользователе
        directed_by = current_user.full_name or current_user.username
        
        # Формируем название лида
        lead_title = f"Сделка от агентов - {candidate_name}"
        
        from bitrix_api import BitrixAPI
        from config import BITRIX_WEBHOOK_URL, SOURCE_AGENT
        
        bitrix_api = BitrixAPI(BITRIX_WEBHOOK_URL)
        
        # Подготавливаем данные для лида
        lead_data = {
            'title': lead_title,
            'candidate_name': candidate_name,
            'candidate_phone': candidate_phone,
            'object_name': object_name,
            'position_name': position_name,
            'directed_by': directed_by,
            'agent_name': agent_name,
            'agent_object': agent_object,
            'comment': '',
            'source_id': SOURCE_AGENT
        }
        
        # Создаём лид с ВСЕМИ файлами
        lead_id = bitrix_api.create_lead_with_files(lead_data, valid_files)
        
        if not lead_id:
            return jsonify({'error': 'Ошибка создания лида в Bitrix24'}), 500
        
        # Логируем действие
        from database import log_user_action
        log_user_action(
            current_user.id,
            'create_lead',
            f"Создан лид: {candidate_name} → {agent_object} (агент: {agent_name}, файлов: {len(valid_files)}, лид {lead_id})",
            request.remote_addr
        )
        
        # Формируем ссылку на лид в Bitrix24
        lead_url = f"https://crm.complect.org/crm/lead/details/{lead_id}/"
        
        return jsonify({
            'success': True,
            'lead_id': lead_id,
            'lead_url': lead_url,
            'files_count': len(valid_files),
            'message': f'Лид создан! ID: {lead_id}, файлов: {len(valid_files)}'
        })
        
    except Exception as e:
        logger.error(f"Ошибка создания лида: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500