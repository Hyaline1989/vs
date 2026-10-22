"""Обезличенные месячные сводки отработанных смен из табелей."""

import json
import os
import re
import tempfile
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from pathlib import Path


STORE_DIR = Path(__file__).resolve().parent / 'data' / 'shift_attendance'
REASONS = {'sheet_missing', 'sheet_ambiguous', 'layout_unknown',
           'calendar_incomplete', 'source_unavailable'}


def days_in_month(month):
    if not isinstance(month, str) or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', month):
        raise ValueError('Некорректный месяц')
    year, number = map(int, month.split('-'))
    return monthrange(year, number)[1]


def validate_snapshot(payload):
    if not isinstance(payload, dict):
        raise ValueError('Ожидается объект JSON')
    month = payload.get('month')
    day_count = days_in_month(month)
    objects = payload.get('objects')
    if not isinstance(objects, list) or not 1 <= len(objects) <= 100:
        raise ValueError('Некорректный список объектов')
    result = []
    seen = set()
    for item in objects:
        if not isinstance(item, dict):
            raise ValueError('Некорректная строка объекта')
        name = item.get('name')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise ValueError('Некорректное название объекта')
        name = name.strip()
        if name.casefold() in seen:
            raise ValueError('Объекты не должны повторяться')
        seen.add(name.casefold())
        counts = item.get('counts')
        if not isinstance(counts, list) or len(counts) != day_count:
            raise ValueError(f'Для каждого объекта требуется {day_count} значений')
        if any(value is not None and (type(value) is not int or not 0 <= value <= 100000)
               for value in counts):
            raise ValueError('Количество должно быть неотрицательным целым числом или null')
        reasons = item.get('reasons', [None] * day_count)
        if (not isinstance(reasons, list) or len(reasons) != day_count or
                any(reason is not None and (not isinstance(reason, str) or reason not in REASONS)
                    for reason in reasons) or
                any((count is None) != (reason is not None)
                    for count, reason in zip(counts, reasons))):
            raise ValueError('Некорректные причины отсутствия данных')
        result.append({'name': name, 'counts': counts, 'reasons': reasons})
    result.sort(key=lambda row: row['name'].casefold())
    return {
        'month': month,
        'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'objects': result,
    }


def snapshot_path(month, store_dir=STORE_DIR):
    days_in_month(month)
    return Path(store_dir) / f'{month}.json'


def read_snapshot(month, store_dir=STORE_DIR):
    try:
        with snapshot_path(month, store_dir).open(encoding='utf-8') as stream:
            return json.load(stream)
    except FileNotFoundError:
        return None


def report_for_period(start, end, store_dir=STORE_DIR):
    """Собрать дневные числа из месячных сводок, не складывая людей за период."""
    dates = []
    day = start
    while day <= end:
        dates.append(day)
        day += timedelta(days=1)

    months = {day.strftime('%Y-%m') for day in dates}
    snapshots = {month: read_snapshot(month, store_dir) for month in months}
    if not any(snapshots.values()):
        return {'status': 'not_loaded', 'from': start.isoformat(), 'to': end.isoformat()}

    objects_by_month = {
        month: {row['name']: row for row in snapshot['objects']}
        for month, snapshot in snapshots.items() if snapshot is not None
    }
    names = sorted({name for rows in objects_by_month.values() for name in rows},
                   key=str.casefold)
    rows = []
    for name in names:
        counts = []
        reasons = []
        for day in dates:
            month = day.strftime('%Y-%m')
            source = objects_by_month.get(month, {}).get(name)
            if source is None:
                counts.append(None)
                reasons.append('month_not_loaded' if snapshots[month] is None else 'object_missing')
            else:
                counts.append(source['counts'][day.day - 1])
                reasons.append(source['reasons'][day.day - 1])
        rows.append({'name': name, 'counts': counts, 'reasons': reasons})

    totals = []
    incomplete = []
    for index in range(len(dates)):
        known = [row['counts'][index] for row in rows if row['counts'][index] is not None]
        totals.append(sum(known) if known else None)
        incomplete.append(len(known) != len(rows))
    return {
        'status': 'ready',
        'from': start.isoformat(), 'to': end.isoformat(),
        'dates': [day.isoformat() for day in dates],
        'objects': rows, 'totals': totals, 'incomplete': incomplete,
    }


def write_snapshot(snapshot, store_dir=STORE_DIR):
    path = snapshot_path(snapshot['month'], store_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix='.shifts-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(snapshot, stream, ensure_ascii=False, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
