# database/worker_status.py
# -*- coding: utf-8 -*-
import sqlite3
import logging
from datetime import datetime, timedelta

from database.db_core import DB_NAME

logger = logging.getLogger(__name__)


def get_worker_statuses(agent_full_name, date_from=None, date_to=None):
    """
    Получает статусы вахтовиков для конкретного агента
    date_from, date_to - строки в формате YYYY-MM-DD
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT id, lead_id, worker_full_name, agent_full_name, deal_date,
                   check_in_date, shift_1_date, shift_5_date, last_synced
            FROM worker_statuses
            WHERE agent_full_name = ?
        '''
        params = [agent_full_name]
        
        if date_from:
            query += ' AND deal_date >= ?'
            params.append(date_from)
        
        if date_to:
            query += ' AND deal_date <= ?'
            params.append(date_to)
        
        query += ' ORDER BY deal_date DESC, worker_full_name'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    except Exception as e:
        logger.error(f"Ошибка при получении статусов вахтовиков: {e}")
        return []


def save_or_update_worker_status(lead_id, worker_full_name, agent_full_name, deal_date,
                                  check_in_date=None, shift_1_date=None, shift_5_date=None):
    """Сохраняет или обновляет статус вахтовика"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Очищаем даты (убираем время, оставляем только YYYY-MM-DD)
        if check_in_date and len(check_in_date) > 10:
            check_in_date = check_in_date[:10]
        if shift_1_date and len(shift_1_date) > 10:
            shift_1_date = shift_1_date[:10]
        if shift_5_date and len(shift_5_date) > 10:
            shift_5_date = shift_5_date[:10]
        if deal_date and len(deal_date) > 10:
            deal_date = deal_date[:10]
        
        cursor.execute('''
            INSERT INTO worker_statuses 
            (lead_id, worker_full_name, agent_full_name, deal_date, 
             check_in_date, shift_1_date, shift_5_date, updated_at, last_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(lead_id) DO UPDATE SET
                worker_full_name = excluded.worker_full_name,
                agent_full_name = excluded.agent_full_name,
                deal_date = excluded.deal_date,
                check_in_date = excluded.check_in_date,
                shift_1_date = excluded.shift_1_date,
                shift_5_date = excluded.shift_5_date,
                updated_at = CURRENT_TIMESTAMP,
                last_synced = CURRENT_TIMESTAMP
        ''', (lead_id, worker_full_name, agent_full_name, deal_date,
              check_in_date, shift_1_date, shift_5_date))
        
        conn.commit()
        conn.close()
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при сохранении статуса вахтовика: {e}")
        return False


def update_worker_status_from_bitrix(lead_id, check_in_date=None, shift_1_date=None, shift_5_date=None):
    """Обновляет статусы вахтовика из данных Bitrix24"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if check_in_date is not None:
            if len(check_in_date) > 10:
                check_in_date = check_in_date[:10]
            updates.append('check_in_date = ?')
            params.append(check_in_date)
        if shift_1_date is not None:
            if len(shift_1_date) > 10:
                shift_1_date = shift_1_date[:10]
            updates.append('shift_1_date = ?')
            params.append(shift_1_date)
        if shift_5_date is not None:
            if len(shift_5_date) > 10:
                shift_5_date = shift_5_date[:10]
            updates.append('shift_5_date = ?')
            params.append(shift_5_date)
        
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            updates.append('last_synced = CURRENT_TIMESTAMP')
            params.append(lead_id)
            cursor.execute(f'''
                UPDATE worker_statuses 
                SET {', '.join(updates)}
                WHERE lead_id = ?
            ''', params)
            conn.commit()
        
        conn.close()
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса вахтовика (lead_id={lead_id}): {e}")
        return False


def delete_old_worker_records(days=365):
    """Удаляет записи старше указанного количества дней"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        cursor.execute('DELETE FROM worker_statuses WHERE deal_date < ?', (cutoff_date,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            logger.info(f"Удалено {deleted} старых записей вахтовиков (старше {days} дней)")
        return deleted
    except Exception as e:
        logger.error(f"Ошибка при удалении старых записей: {e}")
        return 0


def get_worker_status_by_lead_id(lead_id):
    """Получает статус вахтовика по ID лида"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM worker_statuses WHERE lead_id = ?
        ''', (lead_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Ошибка при получении статуса по lead_id: {e}")
        return None