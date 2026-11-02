"""Расчёт выплат за кандидатов, отработавших первую смену."""
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone

from normalizer import ObjectNameNormalizer


def calculate(path, deals, today=None):
    """Сопоставляет сделки со ставкой на дату направления и группирует по сотруднику."""
    normalize = ObjectNameNormalizer().normalize
    today = today or datetime.now(timezone(timedelta(hours=3))).date()
    with closing(sqlite3.connect(path)) as conn:
        objects = {}
        for object_id, name in conn.execute('SELECT id, name FROM objects_settings'):
            objects.setdefault(normalize(name), []).append((object_id, name))
        rates = {
            (object_id, day): (amount, source)
            for object_id, day, amount, source in conn.execute(
                'SELECT object_id, day, amount, source FROM candidate_rates'
            )
        }
        priorities = {}
        for day, name, is_high in conn.execute(
                'SELECT date, object_name, MAX(is_high) FROM daily_snapshots GROUP BY date, object_name'
            ):
            key = (day, normalize(name))
            priorities[key] = priorities.get(key, False) or bool(is_high)

    rows = []
    excluded = []
    for deal in deals:
        try:
            directed = date.fromisoformat(deal.get('directed_date') or '')
            shifted = date.fromisoformat(deal.get('shift_date') or '')
            valid_dates = directed <= shifted <= today
        except (ValueError, TypeError):
            valid_dates = False
        if not valid_dates:
            excluded.append({'deal_id': str(deal.get('deal_id') or ''),
                             'candidate': deal.get('candidate') or 'Без имени',
                             'problem': 'Проверьте даты: первая смена должна быть не раньше направления и не позже сегодняшнего дня'})
            continue
        object_name = (deal.get('object_name') or '').strip()
        matches = objects.get(normalize(object_name), [])
        object_id = matches[0][0] if len(matches) == 1 else None
        saved_rate = rates.get((object_id, deal['directed_date'])) if object_id is not None else None
        if saved_rate:
            rate = saved_rate
        elif object_id is not None:
            rate = (4000, 'priority-default') if priorities.get((deal['directed_date'], normalize(object_name)), False) else (2500, 'default')
        else:
            rate = None
        rows.append({
            'deal_id': str(deal.get('deal_id') or ''),
            'candidate': (deal.get('candidate') or 'Без имени').strip(),
            'staff': (deal.get('staff') or 'Без сотрудника').strip(),
            'object': object_name or 'Объект не указан',
            'directed_date': deal['directed_date'],
            'shift_date': deal['shift_date'],
            'amount': rate[0] if rate else None,
            'rate_source': rate[1] if rate else None,
            'problem': None if rate else (
                'Неоднозначное название объекта' if len(matches) > 1 else
                'Объект не найден в настройках'
            ),
        })

    rows.sort(key=lambda row: (row['staff'].casefold(), row['directed_date'], row['candidate'].casefold()))
    staff = {}
    for row in rows:
        item = staff.setdefault(row['staff'], {'staff': row['staff'], 'candidates': 0, 'amount': 0, 'unrated': 0})
        item['candidates'] += 1
        if row['amount'] is None:
            item['unrated'] += 1
        else:
            item['amount'] += row['amount']
    summary = sorted(staff.values(), key=lambda row: row['staff'].casefold())
    return {
        'summary': summary,
        'rows': rows,
        'excluded': excluded,
        'totals': {
            'candidates': len(rows),
            'amount': sum(row['amount'] or 0 for row in rows),
            'unrated': sum(row['amount'] is None for row in rows),
        },
    }
