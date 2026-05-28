# routes/worker_status.py
# -*- coding: utf-8 -*-
import requests
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging
from datetime import datetime

from database.worker_status import get_worker_statuses, save_or_update_worker_status, get_worker_status_by_lead_id
from bitrix_api import BitrixAPI
from config import BITRIX_WEBHOOK_URL

logger = logging.getLogger(__name__)

worker_status_bp = Blueprint('worker_status', __name__, url_prefix='/api/worker-status')


@worker_status_bp.route('', methods=['GET'])
@login_required
def get_worker_statuses_api():
    """
    Получение статусов вахтовиков для текущего агента
    Параметры: ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    """
    if not current_user.can_view_worker_status():
        return jsonify({'error': 'Forbidden', 'message': 'У вас нет доступа к разделу "Вахтовики"'}), 403
    
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    
    # Валидация дат
    if date_from:
        try:
            datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Неверный формат даты "с"'}), 400
    
    if date_to:
        try:
            datetime.strptime(date_to, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'Неверный формат даты "по"'}), 400
    
    # Получаем полное имя агента из профиля
    agent_full_name = current_user.full_name or current_user.username
    
    # Синхронизируем с Bitrix24
    try:
        bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
        synced = bitrix.sync_worker_statuses_for_agent(agent_full_name, date_from, date_to)
        logger.info(f"Синхронизировано {synced} записей для агента {agent_full_name}")
    except Exception as e:
        logger.error(f"Ошибка синхронизации с Bitrix: {e}")
    
    # Получаем данные из БД с учётом фильтра
    statuses = get_worker_statuses(agent_full_name, date_from, date_to)
    
    # Форматируем ответ
    result = []
    for s in statuses:
        result.append({
            'lead_id': s['lead_id'],
            'worker_full_name': s['worker_full_name'],
            'deal_date': s['deal_date'],
            'check_in_date': s['check_in_date'],
            'shift_1_date': s['shift_1_date'],
            'shift_5_date': s['shift_5_date'],
            'last_synced': s.get('last_synced')
        })
    
    return jsonify({
        'success': True,
        'agent_name': agent_full_name,
        'statuses': result,
        'count': len(result)
    })


@worker_status_bp.route('/sync', methods=['POST'])
@login_required
def force_sync():
    """Принудительная синхронизация статусов с Bitrix24"""
    if not current_user.can_view_worker_status():
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json() or {}
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    
    agent_full_name = current_user.full_name or current_user.username
    
    try:
        bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
        synced = bitrix.sync_worker_statuses_for_agent(agent_full_name, date_from, date_to)
        
        statuses = get_worker_statuses(agent_full_name, date_from, date_to)
        
        return jsonify({
            'success': True,
            'synced_count': synced,
            'total_count': len(statuses),
            'message': f'Синхронизировано {synced} записей'
        })
    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}")
        return jsonify({'error': str(e)}), 500


@worker_status_bp.route('/debug-lead/<int:lead_id>', methods=['GET'])
@login_required
def debug_lead(lead_id):
    """Диагностический эндпоинт - показывает все поля лида (только для админа)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
        lead_data = bitrix.debug_lead_fields(lead_id)
        
        if not lead_data:
            return jsonify({'error': 'Лид не найден'}), 404
        
        # Находим все поля с датами
        date_fields = {}
        for key, value in lead_data.items():
            if 'date' in key.lower() or 'дата' in key.lower() or 'засел' in key.lower() or 'смен' in key.lower():
                date_fields[key] = value
        
        return jsonify({
            'success': True,
            'lead_id': lead_id,
            'date_fields': date_fields,
            'all_fields_keys': list(lead_data.keys())
        })
    except Exception as e:
        logger.error(f"Ошибка диагностики: {e}")
        return jsonify({'error': str(e)}), 500


@worker_status_bp.route('/debug-all-lead-fields/<int:lead_id>', methods=['GET'])
@login_required
def debug_all_lead_fields(lead_id):
    """
    ДИАГНОСТИКА - показывает ВСЕ поля лида и их значения
    Используется для определения правильных названий полей с датами
    """
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
        method = 'crm.lead.get'
        params = {'id': lead_id}
        response = requests.post(f"{bitrix.webhook_url}{method}", json=params, timeout=30)
        result = response.json()
        
        if 'result' in result:
            lead = result['result']
            
            # Собираем все поля с их значениями
            all_fields = {}
            for key, value in lead.items():
                if value:
                    all_fields[key] = str(value)
            
            # Специально ищем поля, содержащие даты
            date_fields = {}
            for key, value in lead.items():
                if value and ('.' in str(value) or '-' in str(value)):
                    val_str = str(value)
                    if '25.05' in val_str or '26.05' in val_str or '27.05' in val_str or '2026-05' in val_str:
                        date_fields[key] = val_str
            
            return jsonify({
                'success': True,
                'lead_id': lead_id,
                'lead_title': lead.get('TITLE'),
                'lead_name': lead.get('NAME'),
                'lead_last_name': lead.get('LAST_NAME'),
                'all_fields_with_values': all_fields,
                'date_fields_found': date_fields
            })
        else:
            return jsonify({'error': 'Лид не найден'}), 404
    except Exception as e:
        logger.error(f"Ошибка диагностики: {e}")
        return jsonify({'error': str(e)}), 500


@worker_status_bp.route('/lead/<int:lead_id>', methods=['GET'])
@login_required
def get_lead_status(lead_id):
    """Получение статуса конкретного лида из Bitrix24"""
    if not current_user.can_view_worker_status():
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
        lead_data = bitrix.get_lead_by_id(lead_id)
        
        if not lead_data:
            return jsonify({'error': 'Лид не найден'}), 404
        
        # Проверяем, что лид принадлежит текущему агенту
        agent_full_name = current_user.full_name or current_user.username
        if lead_data.get('agent_full_name') != agent_full_name:
            return jsonify({'error': 'Доступ запрещён'}), 403
        
        return jsonify({
            'success': True,
            'lead_id': lead_id,
            'worker_full_name': lead_data.get('worker_full_name'),
            'check_in_date': lead_data.get('check_in_date'),
            'shift_1_date': lead_data.get('shift_1_date'),
            'shift_5_date': lead_data.get('shift_5_date')
        })
    except Exception as e:
        logger.error(f"Ошибка при получении статуса лида: {e}")
        return jsonify({'error': str(e)}), 500