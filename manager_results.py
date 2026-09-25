"""Месячная результативность: звонки UIS и когорта направлений Битрикс24."""
import re
from collections import defaultdict
from datetime import date

from config import (
    EXCLUDED_SOURCES, FIELD_AGENT_FIO, FIELD_CC_OPERATOR_REPORT, FIELD_DATE_DIRECTED,
    SOURCE_AGENT, SOURCE_BISHKEK, SOURCE_POTOK,
)
from bitrix_api import CHECK_IN_FIELD, SHIFT_1_FIELD, SHIFT_5_FIELD
from manager_efficiency import is_excluded_manager

METRICS = ('calls', 'directed', 'checked_in', 'shift_1', 'shift_5')
PREFIXES = ('(bitrix24)', 'поток', 'нижегородская', 'виртуальный', 'комплект')


def manager_key(value):
    name = re.sub(r'\s+', ' ', (value or '').strip()).casefold()
    while True:
        for prefix in PREFIXES:
            if name.startswith(prefix + ' '):
                name = name[len(prefix):].strip()
                break
        else:
            return name


def eligible_name(value):
    name = (value or '').strip()
    key = manager_key(name)
    return bool(key) and not is_excluded_manager(name) and not key.startswith(('спутник', 'опер'))


def stage_reached(value, directed_date):
    if not value or value == 'N':
        return False
    try:
        return date.fromisoformat(str(value)[:10]) >= directed_date
    except ValueError:
        return False


def build_manager_results(calls, deals, previous=None):
    stats = defaultdict(lambda: {metric: 0 for metric in METRICS})
    names = {}
    systems = {}

    for call in calls:
        name = call.get('employee_name') or ''
        if not eligible_name(name):
            continue
        system = call.get('system') or ''
        key = (system, manager_key(name))
        names.setdefault(key, name)
        systems[key] = system
        if 'count' in call:
            stats[key]['calls'] += int(call['count'])
            continue
        direction = call.get('direction')
        duration = int(call.get('clean_talk_duration') or 0)
        if (direction == 'in' and call.get('is_talked') and duration > 0) or direction == 'out':
            stats[key]['calls'] += 1

    for deal in deals:
        source = deal.get('SOURCE_ID')
        if source in EXCLUDED_SOURCES or source in (SOURCE_AGENT, SOURCE_BISHKEK):
            continue
        if deal.get(FIELD_AGENT_FIO):
            continue
        name = deal.get(FIELD_CC_OPERATOR_REPORT) or ''
        if not eligible_name(name):
            continue
        directed_raw = deal.get(FIELD_DATE_DIRECTED)
        try:
            directed_date = date.fromisoformat(str(directed_raw)[:10])
        except ValueError:
            continue
        system = 'Поток' if source == SOURCE_POTOK else 'Комплект'
        key = (system, manager_key(name))
        names.setdefault(key, name)
        systems[key] = system
        item = stats[key]
        item['directed'] += 1
        item['checked_in'] += stage_reached(deal.get(CHECK_IN_FIELD), directed_date)
        item['shift_1'] += stage_reached(deal.get(SHIFT_1_FIELD), directed_date)
        item['shift_5'] += stage_reached(deal.get(SHIFT_5_FIELD), directed_date)

    rows = []
    for key, item in stats.items():
        calls_count = item['calls']
        rates = {metric: item[metric] / calls_count if calls_count else 0 for metric in METRICS[1:]}
        prior = (previous or {}).get(key)
        change = {
            metric: (rates[metric] / prior[metric] - 1 if prior and prior.get(metric) else None)
            for metric in METRICS[1:]
        }
        rows.append({
            'system': systems[key], 'manager': names[key], 'key': key[1],
            **item, 'rates': rates, 'change': change,
        })
    def rank(metric, value):
        return 1 + sum(other[metric] > value for other in rows)

    for row in rows:
        row['rating'] = round(
            rank('shift_1', row['shift_1']) * 0.4
            + rank('directed', row['directed']) * 0.3
            + (1 + sum(other['rates']['directed'] > row['rates']['directed'] for other in rows)) * 0.1
            + (1 + sum(other['rates']['checked_in'] > row['rates']['checked_in'] for other in rows)) * 0.2,
            2
        )
    rows.sort(key=lambda row: (row['rating'], row['manager'].casefold()))
    totals = {metric: sum(row[metric] for row in rows) for metric in METRICS}
    totals['rates'] = {
        metric: totals[metric] / totals['calls'] if totals['calls'] else 0
        for metric in METRICS[1:]
    }
    return rows, totals
