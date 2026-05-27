# routes/worker_status.py
# -*- coding: utf-8 -*-
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging
from datetime import datetime

from database.worker_status import get_worker_statuses
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
    if not current_user.can_view_selection():
        return jsonify({'error': 'Forbidden'}), 403
    
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
    
    # Получаем полное имя агента из профиля (именно ФИО, не username)
    agent_full_name = current_user.full_name or current_user.username
    
    # Сначала синхронизируем с Bitrix24
    try:
        bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
        synced = bitrix.sync_worker_statuses_for_agent(agent_full_name, date_from, date_to)
        logger.info(f"Синхронизировано {synced} записей для агента {agent_full_name}")
    except Exception as e:
        logger.error(f"Ошибка синхронизации с Bitrix: {e}")
        # Продолжаем с локальными данными
    
    # Получаем данные из БД
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
    if not current_user.can_view_selection():
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json() or {}
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    
    agent_full_name = current_user.full_name or current_user.username
    
    try:
        bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
        synced = bitrix.sync_worker_statuses_for_agent(agent_full_name, date_from, date_to)
        
        return jsonify({
            'success': True,
            'synced_count': synced,
            'message': f'Синхронизировано {synced} записей'
        })
    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}")
        return jsonify({'error': str(e)}), 500