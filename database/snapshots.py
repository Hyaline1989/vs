# database/snapshots.py
# -*- coding: utf-8 -*-
import sqlite3
import logging

from database.db_core import DB_NAME

logger = logging.getLogger(__name__)


def get_priority_history(from_date, to_date):
    """Читает сохранённые дни, включая дни без приоритетов; не скрывает ошибки."""
    from contextlib import closing
    from datetime import date, timedelta
    with closing(sqlite3.connect(DB_NAME)) as conn:
        rows = conn.execute('''
            SELECT date, object_name, MAX(is_high)
            FROM daily_snapshots WHERE date BETWEEN ? AND ?
            GROUP BY date, object_name
        ''', (from_date, to_date)).fetchall()
    saved = {}
    for day, name, is_high in rows:
        saved.setdefault(day, set())
        if is_high:
            saved[day].add(name)
    result = []
    day, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
    while day <= end:
        key = day.isoformat()
        result.append({'date': key, 'saved': key in saved,
                       'objects': sorted(saved.get(key, ()), key=str.casefold)})
        day += timedelta(days=1)
    return result


def save_daily_snapshot(date, object_name, office_name, count, plan=0, is_high=False):
    """Сохраняет или обновляет снапшот за день"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO daily_snapshots (date, object_name, office_name, count, plan, is_high)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, object_name, office_name) DO UPDATE SET
                count = excluded.count,
                plan = excluded.plan,
                is_high = excluded.is_high,
                created_at = CURRENT_TIMESTAMP
        ''', (date, object_name, office_name, count, plan, 1 if is_high else 0))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении снапшота: {e}")
        return False


def save_daily_snapshots_batch(date, data):
    """Сохраняет пачку снапшотов за день"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        for item in data:
            cursor.execute('''
                INSERT INTO daily_snapshots (date, object_name, office_name, count, plan, is_high)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, object_name, office_name) DO UPDATE SET
                    count = excluded.count,
                    plan = excluded.plan,
                    is_high = excluded.is_high,
                    created_at = CURRENT_TIMESTAMP
            ''', (date, item['object_name'], item['office_name'], item['count'], item['plan'], 1 if item.get('is_high', False) else 0))
        
        from candidate_rates import sync_priority_rates
        sync_priority_rates(conn, date)
        conn.commit()
        conn.close()
        logger.info(f"✅ Сохранено {len(data)} снапшотов за {date}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при пакетном сохранении снапшотов: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


def get_snapshot_report(from_date, to_date):
    """Получает отчёт из снапшотов (быстро, без запросов к Bitrix)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT date, object_name,
                   MAX(plan) as plan,
                   MAX(is_high) as is_high,
                   SUM(CASE WHEN office_name = 'complect' THEN count ELSE 0 END) as complect,
                   SUM(CASE WHEN office_name = 'potok' THEN count ELSE 0 END) as potok,
                   SUM(CASE WHEN office_name = 'gorkiy52' THEN count ELSE 0 END) as gorkiy,
                   SUM(CASE WHEN office_name = 'agent' THEN count ELSE 0 END) as agent,
                   SUM(CASE WHEN office_name = 'bishkek' THEN count ELSE 0 END) as bishkek
            FROM daily_snapshots
            WHERE date BETWEEN ? AND ?
            GROUP BY date, object_name
            ORDER BY date, object_name
        ''', (from_date, to_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = {}
        for row in rows:
            date = row['date']
            if date not in result:
                result[date] = []
            
            result[date].append({
                'object_name': row['object_name'],
                'plan': row['plan'] or 0,
                'is_high': bool(row['is_high']),
                'complect': row['complect'] or 0,
                'potok': row['potok'] or 0,
                'gorkiy': row['gorkiy'] or 0,
                'agent': row['agent'] or 0,
                'bishkek': row['bishkek'] or 0
            })
        
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении отчёта из снапшотов: {e}")
        return {}


def check_snapshot_exists(date):
    """Проверяет, есть ли уже снапшот за указанную дату"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM daily_snapshots WHERE date = ?', (date,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        logger.error(f"Ошибка при проверке снапшота: {e}")
        return False


def delete_snapshots_for_date(date):
    """Удаляет снапшоты за указанную дату (для пересохранения)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM daily_snapshots WHERE date = ?', (date,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        logger.info(f"Удалено {deleted} снапшотов за {date}")
        return deleted
    except Exception as e:
        logger.error(f"Ошибка при удалении снапшотов: {e}")
        return 0
