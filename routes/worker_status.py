# routes/worker_status.py
# -*- coding: utf-8 -*-
import requests
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging
from datetime import datetime
import sqlite3

from database.worker_status import get_worker_statuses, save_or_update_worker_status, get_worker_status_by_lead_id
from database import log_user_action, DB_NAME
from bitrix_api import BitrixAPI, AGENT_NAME_FIELD
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
    """
    Принудительная синхронизация статусов с Bitrix24.
    Автоматически исправляет имя агента, если в Bitrix оно отличается от профиля.
    """
    if not current_user.can_view_worker_status():
        return jsonify({'error': 'Forbidden'}), 403
    
    data = request.get_json() or {}
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    
    agent_full_name = current_user.full_name or current_user.username
    
    try:
        bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
        
        # ========== АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ ИМЕНИ АГЕНТА ==========
        fixed_count = 0
        
        # Проверяем, есть ли лиды с другим вариантом имени
        name_parts = agent_full_name.split()
        alternative_names = []
        
        if len(name_parts) >= 2:
            # Если имя состоит из двух частей - пробуем переставить
            alt1 = f"{name_parts[1]} {name_parts[0]}"
            if alt1 != agent_full_name:
                alternative_names.append(alt1)
        
        # Проверяем каждый альтернативный вариант
        for alt_name in alternative_names:
            # Ищем лиды с альтернативным именем
            alt_filter = {AGENT_NAME_FIELD: alt_name}
            alt_leads = bitrix._get_all_leads_raw_for_worker(alt_filter)
            
            if alt_leads:
                logger.info(f"🔍 Найдено {len(alt_leads)} лидов с альтернативным именем '{alt_name}'")
                
                # Обновляем их на правильное имя
                for lead in alt_leads:
                    lead_id = lead.get('ID')
                    if not lead_id:
                        continue
                    try:
                        method = 'crm.lead.update'
                        params = {
                            'id': lead_id,
                            'fields': {
                                AGENT_NAME_FIELD: agent_full_name
                            }
                        }
                        response = requests.post(f"{BITRIX_WEBHOOK_URL}{method}", json=params, timeout=30)
                        result = response.json()
                        if 'result' in result:
                            fixed_count += 1
                            logger.info(f"✅ Исправлено имя агента для лида {lead_id}: {alt_name} → {agent_full_name}")
                    except Exception as e:
                        logger.error(f"Ошибка обновления лида {lead_id}: {e}")
                
                # Обновляем локальную БД
                if fixed_count > 0:
                    conn = sqlite3.connect(DB_NAME)
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE worker_statuses 
                        SET agent_full_name = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE agent_full_name = ?
                    ''', (agent_full_name, alt_name))
                    db_updated = cursor.rowcount
                    conn.commit()
                    conn.close()
                    logger.info(f"✅ Обновлено {db_updated} записей в локальной БД")
        
        # ========== ОСНОВНАЯ СИНХРОНИЗАЦИЯ ==========
        synced = bitrix.sync_worker_statuses_for_agent(agent_full_name, date_from, date_to)
        
        statuses = get_worker_statuses(agent_full_name, date_from, date_to)
        
        message = f'Синхронизировано {synced} записей'
        if fixed_count > 0:
            message += f', исправлено имён агентов: {fixed_count}'
        
        return jsonify({
            'success': True,
            'synced_count': synced,
            'fixed_names_count': fixed_count,
            'total_count': len(statuses),
            'message': message
        })
    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}")
        return jsonify({'error': str(e)}), 500


# ========== ДИАГНОСТИЧЕСКИЙ ЭНДПОИНТ ДЛЯ СДЕЛКИ ==========

@worker_status_bp.route('/debug/deal/<int:deal_id>', methods=['GET'])
@login_required
def debug_deal(deal_id):
    """
    Диагностика конкретной сделки - проверяет все поля и причины отсутствия
    """
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    agent_full_name = current_user.full_name or current_user.username
    bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
    
    # 1. Получаем данные сделки
    method = 'crm.deal.get'
    params = {'id': deal_id}
    
    try:
        response = requests.post(f"{BITRIX_WEBHOOK_URL}{method}", json=params, timeout=30)
        result = response.json()
        
        if 'result' not in result:
            return jsonify({'error': 'Сделка не найдена'}), 404
        
        deal = result['result']
        
        # 2. Проверяем ключевые поля
        deal_info = {
            'id': deal.get('ID'),
            'title': deal.get('TITLE'),
            'source_id': deal.get('SOURCE_ID'),
            'date_directed': deal.get('UF_CRM_1684488775220'),  # Дата направлен на объект
            'company_id': deal.get('UF_CRM_642A972B79B02'),    # Объект (компания)
            'agent_name_field': deal.get(AGENT_NAME_FIELD),    # ФИО агента
            'agent_name_field_raw': AGENT_NAME_FIELD,
            'shift_1_date': deal.get('UF_CRM_1685531338652'),  # Дата отработал 1 смену
            'cc_operator': deal.get('UF_CRM_64819E13601C3'),   # Сотрудник Колл-центра
            'cc_operator_report': deal.get('UF_CRM_68F1ED4DB3EE8'), # Сотрудник Колл-центра (ОТЧЕТ)
            'lead_id': deal.get('LEAD_ID'),                    # Связанный лид
        }
        
        # 3. Проверяем, соответствует ли сделка критериям для отображения
        checks = {
            'has_agent_name': bool(deal_info['agent_name_field']),
            'agent_name_matches': deal_info['agent_name_field'] == agent_full_name,
            'has_date_directed': bool(deal_info['date_directed']),
            'source_not_excluded': deal_info.get('source_id') not in ['UC_5LI24O', 'UC_1S4DWZ'],  # Перевахтовка, Приведи друга
            'has_shift_1_date': bool(deal_info['shift_1_date']),
            'has_lead': bool(deal_info['lead_id']),
        }
        
        # 4. Проверяем, есть ли эта сделка в локальной БД
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM worker_statuses WHERE lead_id = ?
        ''', (deal_id,))
        local_record = cursor.fetchone()
        conn.close()
        
        # 5. Если есть лид, проверяем его
        lead_info = None
        if deal_info['lead_id']:
            method_lead = 'crm.lead.get'
            params_lead = {'id': deal_info['lead_id']}
            try:
                lead_response = requests.post(f"{BITRIX_WEBHOOK_URL}{method_lead}", json=params_lead, timeout=30)
                lead_result = lead_response.json()
                if 'result' in lead_result:
                    lead = lead_result['result']
                    lead_info = {
                        'id': lead.get('ID'),
                        'title': lead.get('TITLE'),
                        'agent_name': lead.get(AGENT_NAME_FIELD),
                        'created': lead.get('DATE_CREATE'),
                        'has_agent_name': bool(lead.get(AGENT_NAME_FIELD)),
                        'agent_name_matches': lead.get(AGENT_NAME_FIELD) == agent_full_name,
                    }
            except Exception as e:
                lead_info = {'error': str(e)}
        
        # 6. Формируем результат
        all_checks_passed = all([
            checks['has_agent_name'],
            checks['agent_name_matches'],
            checks['has_date_directed'],
            checks['source_not_excluded'],
        ])
        
        return jsonify({
            'deal': deal_info,
            'checks': checks,
            'local_record_exists': bool(local_record),
            'local_record': local_record,
            'lead_info': lead_info,
            'agent_full_name': agent_full_name,
            'summary': {
                'is_visible': all_checks_passed,
                'reason': _get_reason(checks, lead_info)
            },
            'suggestions': _get_suggestions(checks, lead_info, bool(local_record))
        })
        
    except Exception as e:
        logger.error(f"Ошибка диагностики сделки {deal_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _get_reason(checks, lead_info=None):
    """Возвращает причину, почему сделка не отображается"""
    if not checks['has_agent_name']:
        return '❌ В сделке не заполнено поле "ФИО агента" (UF_CRM_1708339537928)'
    if not checks['agent_name_matches']:
        return f'❌ Имя агента в сделке не совпадает с профилем. В сделке: "{checks.get("agent_name_field", "")}", в профиле: "{checks.get("agent_full_name", "")}"'
    if not checks['has_date_directed']:
        return '❌ В сделке не заполнена дата направления (UF_CRM_1684488775220)'
    if not checks['source_not_excluded']:
        return '❌ Источник сделки исключён из отображения (Перевахтовка UC_5LI24O или Приведи друга UC_1S4DWZ)'
    if not checks['has_lead']:
        return '⚠️ У сделки нет связанного лида (поле LEAD_ID пустое)'
    if lead_info and not lead_info.get('agent_name_matches', True):
        return f'⚠️ В лиде не совпадает имя агента. В лиде: "{lead_info.get("agent_name", "")}"'
    return '✅ Все проверки пройдены'


def _get_suggestions(checks, lead_info, has_local_record):
    """Возвращает рекомендации по исправлению"""
    suggestions = []
    
    if not checks['has_agent_name']:
        suggestions.append('Заполните поле "ФИО агента" (UF_CRM_1708339537928) в сделке')
    
    if not checks['agent_name_matches']:
        suggestions.append(f'Измените поле "ФИО агента" в сделке на "{checks.get("agent_full_name", "")}"')
    
    if not checks['has_date_directed']:
        suggestions.append('Заполните дату направления (UF_CRM_1684488775220) в сделке')
    
    if not checks['source_not_excluded']:
        suggestions.append('Измените источник сделки (SOURCE_ID) на другой, не исключённый')
    
    if not checks['has_lead']:
        suggestions.append('Создайте лид для этой сделки (заполните поле LEAD_ID)')
    
    if lead_info and not lead_info.get('agent_name_matches', True):
        suggestions.append(f'Обновите поле "ФИО агента" в лиде {lead_info.get("id")} на "{checks.get("agent_full_name", "")}"')
    
    if not has_local_record:
        suggestions.append('Нажмите кнопку "Синхронизировать" в разделе Вахтовики для добавления записи в локальную БД')
    
    if not suggestions:
        suggestions.append('Все проверки пройдены. Если сделка не отображается, возможно, проблема в фильтрах дат.')
    
    return suggestions


# ========== ДИАГНОСТИЧЕСКИЙ ЭНДПОИНТ ДЛЯ ЛИДА ==========

@worker_status_bp.route('/debug/lead/<int:lead_id>', methods=['GET'])
@login_required
def debug_lead(lead_id):
    """Диагностика лида - показывает все поля лида (только для админа)"""
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


@worker_status_bp.route('/debug/all-lead-fields/<int:lead_id>', methods=['GET'])
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
            
            all_fields = {}
            for key, value in lead.items():
                if value:
                    all_fields[key] = str(value)
            
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


# ========== ДИАГНОСТИЧЕСКИЙ ЭНДПОИНТ ДЛЯ АГЕНТА ==========

@worker_status_bp.route('/debug/agent-check', methods=['GET'])
@login_required
def debug_agent_check():
    """
    Диагностика: проверяет, какие данные хранятся в Bitrix для агента
    """
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    agent_full_name = current_user.full_name or current_user.username
    bitrix = BitrixAPI(BITRIX_WEBHOOK_URL)
    
    # Проверяем, какие лиды есть с этим именем
    filter_params = {
        AGENT_NAME_FIELD: agent_full_name
    }
    
    leads = bitrix._get_all_leads_raw_for_worker(filter_params)
    
    # Также проверяем, какие лиды есть с другим вариантом имени
    name_parts = agent_full_name.split()
    alternative_names = []
    
    if len(name_parts) >= 2:
        alt1 = f"{name_parts[1]} {name_parts[0]}"
        if alt1 != agent_full_name:
            alternative_names.append(alt1)
        alternative_names.append(name_parts[0])
        alternative_names.append(name_parts[1])
    
    alt_leads = []
    for alt_name in alternative_names:
        if alt_name != agent_full_name:
            alt_filter = {AGENT_NAME_FIELD: alt_name}
            alt_results = bitrix._get_all_leads_raw_for_worker(alt_filter)
            if alt_results:
                alt_leads.append({
                    'name': alt_name,
                    'count': len(alt_results),
                    'leads': alt_results[:5]  # первые 5 для примера
                })
    
    return jsonify({
        'current_agent_name': agent_full_name,
        'leads_found_with_current_name': len(leads),
        'leads_sample': leads[:5] if leads else [],
        'alternative_names_found': alt_leads,
        'suggestion': 'Если лиды найдены с другим вариантом имени, нажмите кнопку "Синхронизировать" для автоматического исправления'
    })