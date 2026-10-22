"""Хранение только обезличенных месячных итогов планового убытия."""

import json
import os
import re
import tempfile
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path


STORE_DIR = Path(__file__).resolve().parent / 'data' / 'planned_departures'
ALLOWED_WARNINGS = {
    'sheet_missing', 'sheet_ambiguous', 'layout_unknown', 'calendar_incomplete',
    'previous_month_missing', 'source_unavailable', 'duplicate_names',
}


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
        warnings = item.get('warnings', [])
        if (not isinstance(warnings, list) or len(warnings) > 10 or
                any(not isinstance(code, str) or code not in ALLOWED_WARNINGS for code in warnings)):
            raise ValueError('Некорректные предупреждения')
        reasons = item.get('reasons', [None] * day_count)
        if (not isinstance(reasons, list) or len(reasons) != day_count or
                any(reason is not None and
                    (not isinstance(reason, str) or reason not in ALLOWED_WARNINGS)
                    for reason in reasons) or
                any(count is not None and reason is not None
                    for count, reason in zip(counts, reasons))):
            raise ValueError('Некорректные причины отсутствия данных')
        result.append({
            'name': name, 'counts': counts, 'reasons': reasons,
            'warnings': sorted(set(warnings)),
        })

    result.sort(key=lambda row: row['name'].casefold())
    return {
        'month': month,
        'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'objects': result,
    }


def totals_for(snapshot):
    count = days_in_month(snapshot['month'])
    return [None if any(row['counts'][day] is None for row in snapshot['objects'])
            else sum(row['counts'][day] for row in snapshot['objects'])
            for day in range(count)]


def snapshot_path(month, store_dir=STORE_DIR):
    days_in_month(month)
    return Path(store_dir) / f'{month}.json'


def read_snapshot(month, store_dir=STORE_DIR):
    path = snapshot_path(month, store_dir)
    try:
        with path.open(encoding='utf-8') as stream:
            return json.load(stream)
    except FileNotFoundError:
        return None


def write_snapshot(snapshot, store_dir=STORE_DIR):
    path = snapshot_path(snapshot['month'], store_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix='.planned-', suffix='.tmp', dir=path.parent)
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
