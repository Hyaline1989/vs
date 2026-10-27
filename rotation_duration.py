"""Расчёт длительности вахт по псевдонимизированным отметкам. Без SQLite."""
import re
import statistics
from datetime import date, timedelta, datetime, timezone
from pathlib import Path

from report_refresh_store import _locked, _read, _write, STORE_DIR as REFRESH_DIR
from shift_attendance_store import days_in_month, REASONS

STORE_DIR = Path(__file__).resolve().parent / 'data' / 'rotation_duration'
CODES = {'W', 'В', 'Б', 'СТ', 'З', 'УБ', 'УВ', 'ОВ', 'П', '?'}
ENDS = {'УБ', 'УВ', 'ОВ', 'П'}
METRICS = [
    ('mean', 'Средняя', [('count', 'Людей'), ('sum', 'Сумма смен ≤55'), ('mean', 'Средняя, смен')]),
    ('trimmed', 'Усечённая средняя', [('count', 'Людей'), ('trim', 'Отсечено с каждой стороны'), ('remaining', 'Осталось'), ('trimmed', 'Средняя, смен')]),
    ('median', 'Медиана', [('count', 'Людей'), ('median', 'Медиана, смен')]),
    ('early', 'Убыли за 7 дней', [('count', 'Общий штат'), ('early', 'Убывших'), ('early_share', 'Доля')]),
    ('success', 'Завершили вахту', [('count', 'Общий штат'), ('success', 'Завершивших'), ('success_share', 'Доля')]),
    ('cohort', 'Когорта', [('cohort_count', 'Заехавших'), ('cohort_sum', 'Сумма смен ≤55'), ('cohort_mean', 'Средняя, смен'), ('cohort_inferred', 'По первой смене')]),
]
NOTES = [
    'Один человек — одна максимальная вахта. Максимум выбирается до ограничения 55 сменами.',
    'При равной длине выбирается более поздняя вахта. Дубли смен за день считаются один раз.',
    'Бригадиры, менеджеры, АУП и люди без рабочих смен исключаются.',
    'Перерыв после убытия менее 8 дней объединяет продолжения внутри объекта; от 8 дней разделяет.',
    'Новое заселение после 8 дней без активных отметок также начинает отдельную вахту.',
    'Раннее убытие: УБ, УВ, ОВ или П в первые 7 календарных дней от первой смены.',
    'Завершение: ОВ в конце выбранной вахты или не менее 55 фактических смен.',
    'В когорте дата заезда берётся по З, иначе по первой смене. Выбирается максимальная вахта когорты.',
    'По компании человек учитывается один раз; смены разных объектов не складываются. Исключённая роль на любом объекте исключает человека полностью.',
    'Расчёт только по доступным дням периода. Вахта могла начаться раньше периода. Полные тёзки неразличимы.',
]


def months_between(start, end):
    cursor = start.replace(day=1)
    while cursor <= end:
        yield cursor.strftime('%Y-%m')
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)


def validate_part(payload):
    if not isinstance(payload, dict):
        raise ValueError('Ожидается JSON')
    month = payload.get('month')
    days = days_in_month(month)
    for field in ('batch_id', 'key_id'):
        if not isinstance(payload.get(field), str) or not re.fullmatch(r'[0-9a-f]{32,64}', payload[field]):
            raise ValueError('Некорректный идентификатор')
    names = payload.get('expected_objects')
    if (not isinstance(names, list) or not 1 <= len(names) <= 100 or
            any(not isinstance(n, str) or not 1 <= len(n.strip()) <= 120 for n in names) or
            len(set(names)) != len(names)):
        raise ValueError('Некорректный список объектов')
    obj = payload.get('object')
    if not isinstance(obj, dict) or obj.get('name') not in names:
        raise ValueError('Неизвестный объект')
    reason = obj.get('reason')
    if reason is not None and reason not in REASONS:
        raise ValueError('Неизвестная причина отсутствия данных')
    available = obj.get('available')
    if not isinstance(available, list) or len(available) != days or any(type(x) is not bool for x in available):
        raise ValueError('Некорректный календарь')
    people = obj.get('people')
    if not isinstance(people, list) or len(people) > 10000 or (reason and people):
        raise ValueError('Некорректный список людей')
    cleaned, seen = [], set()
    for p in people:
        if not isinstance(p, dict) or not isinstance(p.get('id'), str) or not re.fullmatch(r'[0-9a-f]{64}', p['id']):
            raise ValueError('Некорректный код человека')
        if p['id'] in seen or type(p.get('excluded')) is not bool:
            raise ValueError('Дубли людей или некорректное исключение')
        seen.add(p['id'])
        marks = p.get('marks')
        if (not isinstance(marks, list) or len(marks) != days or any(
                not isinstance(m, list) or len(m) > len(CODES) or
                any(not isinstance(c, str) or c not in CODES for c in m) for m in marks)):
            raise ValueError('Некорректные отметки смен')
        cleaned.append({'id': p['id'], 'excluded': p['excluded'], 'marks': [sorted(set(m)) for m in marks]})
    return {'month': month, 'batch_id': payload['batch_id'], 'key_id': payload['key_id'],
            'expected_objects': names, 'object': {'name': obj['name'], 'reason': reason,
                                                'available': available, 'people': cleaned}}


def save_part(part, store_dir=STORE_DIR):
    """Публикуем месяц целиком, только когда пришли все его объекты."""
    root = Path(store_dir)
    with _locked(root):
        stage_path = root / ('pending-' + part['month'] + '.json')
        stage = _read(stage_path)
        if not stage or stage['batch_id'] != part['batch_id']:
            stage = {k: part[k] for k in ('month', 'batch_id', 'key_id', 'expected_objects')}
            stage['objects'] = {}
        if stage['key_id'] != part['key_id'] or stage['expected_objects'] != part['expected_objects']:
            raise ValueError('Настройки выгрузки изменились. Повторите обновление месяца')
        stage['objects'][part['object']['name']] = part['object']
        _write(stage_path, stage)
        completed = len(stage['objects']) == len(stage['expected_objects'])
        if completed:
            _write(root / (part['month'] + '.json'), {
                'month': part['month'], 'key_id': part['key_id'],
                'batch_id': part['batch_id'],
                'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'objects': [stage['objects'][n] for n in stage['expected_objects']],
            })
        return completed


def episodes(days, start, end):
    work = sorted(d for d, marks in days.items() if 'W' in marks)
    if not work:
        return []
    groups = [[work[0]]]
    for previous, following in zip(work, work[1:]):
        between = sorted(d for d in days if previous < d < following)
        departed = [d for d in between if days[d] & ENDS]
        arrived = [d for d in between if 'З' in days[d]]
        split = bool(departed and (following - departed[0]).days >= 8)
        if (not split and arrived and (following - previous).days - 1 >= 8 and
                not any(days[d] & {'В', 'Б', 'СТ'} for d in between if d < arrived[-1])):
            split = True
        if split:
            groups.append([])
        groups[-1].append(following)
    result = []
    for i, group in enumerate(groups):
        limit = groups[i + 1][0] if i + 1 < len(groups) else end + timedelta(days=1)
        endings = sorted(d for d in days if group[-1] < d < limit and days[d] & ENDS and 'W' not in days[d])
        departed = endings[0] if endings else None
        lower = groups[i - 1][-1] if i else start - timedelta(days=1)
        arrivals = sorted(d for d in days if lower < d <= group[0] and 'З' in days[d])
        arrival = arrivals[-1] if arrivals else group[0]
        result.append({'actual': len(group), 'shifts': min(55, len(group)), 'first': group[0],
                       'arrival': arrival, 'inferred': not bool(arrivals),
                       'early': bool(departed and (departed - group[0]).days < 7),
                       'success': len(group) >= 55 or bool(departed and 'ОВ' in days[departed])})
    return result


def longest(items):
    return max(items, key=lambda x: (x['actual'], x['first']))


def statistics_for(people, cohort):
    values = sorted(x['shifts'] for x in people)
    n, k = len(values), len(values) // 10
    early = sum(x['early'] for x in people)
    success = sum(x['success'] for x in people)
    cv = [x['shifts'] for x in cohort]
    return {'count': n, 'sum': sum(values), 'mean': statistics.mean(values) if n else None,
            'trim': k, 'remaining': n - k * 2,
            'trimmed': statistics.mean(values[k:n-k]) if n else None,
            'median': statistics.median(values) if n else None, 'early': early,
            'early_share': early / n if n else None, 'success': success,
            'success_share': success / n if n else None,
            'cohort_count': len(cv), 'cohort_sum': sum(cv),
            'cohort_mean': statistics.mean(cv) if cv else None,
            'cohort_inferred': sum(x['inferred'] for x in cohort)}


def saved_loading_status(months, snapshots, refresh_dir=REFRESH_DIR):
    """Только опубликованные месяцы; старый результат не равен новому пересчёту."""
    details = []
    for month in months:
        snapshot = snapshots[month]
        task = _read(Path(refresh_dir) / 'rotations' / (month + '.json'))
        newer = bool(task and (not snapshot or
            task['requested_at'] > snapshot['updated_at']))
        details.append({'month': month, 'saved': bool(snapshot),
                        'parts': len(snapshot['objects']) if snapshot else 0,
                        'saved_at': snapshot['updated_at'] if snapshot else None,
                        'refresh_status': task['status'] if newer else None})
    saved = [d for d in details if d['saved']]
    complete = len(saved) == len(months)
    return {'months_saved': len(saved), 'months_total': len(months),
            'parts_saved': sum(d['parts'] for d in saved),
            'parts_total': sum(d['parts'] for d in saved) if complete else None,
            'complete': complete,
            'latest_saved_at': max((d['saved_at'] for d in saved), default=None),
            'oldest_saved_at': min((d['saved_at'] for d in saved), default=None),
            'months': details}


def build_report(start, end, cohort, mode='objects', store_dir=STORE_DIR, refresh_dir=REFRESH_DIR):
    if mode not in {'objects', 'company'}:
        raise ValueError('Неизвестный вариант отчёта')
    days_in_month(cohort)
    if start > end or (end - start).days > 365 or not start.strftime('%Y-%m') <= cohort <= end.strftime('%Y-%m'):
        raise ValueError('Выберите период до 366 дней и месяц когорты внутри периода')
    months = list(months_between(start, end))
    snapshots = {m: _read(Path(store_dir) / (m + '.json')) for m in months}
    loading = saved_loading_status(months, snapshots, refresh_dir)
    if not any(snapshots.values()):
        return {'status': 'not_loaded', 'loading': loading}
    if len({s['key_id'] for s in snapshots.values() if s}) != 1:
        raise ValueError('Изменился ключ анонимных кодов. Обновите все месяцы выбранного периода')
    names = sorted({o['name'] for s in snapshots.values() if s for o in s['objects']}, key=str.casefold)
    objects, globally_excluded = {}, set()
    for name in names:
        people, excluded, warnings, coverage = {}, set(), [], []
        for month, snapshot in snapshots.items():
            source = next((o for o in snapshot['objects'] if o['name'] == name), None) if snapshot else None
            if not source or source['reason']:
                warnings.append(month + ': ' + (source['reason'] if source else 'month_not_loaded'))
                continue
            coverage.append(month)
            missing = False
            for index, available in enumerate(source['available']):
                day = date.fromisoformat(month + '-01') + timedelta(days=index)
                if start <= day <= end and not available:
                    missing = True
            if missing:
                warnings.append(month + ': calendar_incomplete')
            for p in source['people']:
                if p['excluded']:
                    excluded.add(p['id'])
                days = people.setdefault(p['id'], {})
                for index, marks in enumerate(p['marks']):
                    day = date.fromisoformat(month + '-01') + timedelta(days=index)
                    if start <= day <= end and source['available'][index]:
                        days.setdefault(day, set()).update(marks)
        globally_excluded.update(excluded)
        selected, selected_cohort = {}, {}
        for pid, days in people.items():
            if pid in excluded:
                continue
            runs = episodes(days, start, end)
            if runs:
                selected[pid] = longest(runs)
            cr = [r for r in runs if r['arrival'].strftime('%Y-%m') == cohort]
            if cr:
                selected_cohort[pid] = longest(cr)
        objects[name] = (selected, selected_cohort, warnings, coverage)
    rows = []
    if mode == 'objects':
        for name, (selected, cr, warnings, coverage) in objects.items():
            metrics = statistics_for(selected.values(), cr.values()) if coverage else {k: None for k in statistics_for([], [])}
            rows.append({'name': name, **metrics, 'warnings': warnings, 'coverage': coverage})
    else:
        combined, combined_cohort, warnings = {}, {}, []
        for name, (selected, cr, issues, _) in objects.items():
            warnings.extend(name + ': ' + issue for issue in issues)
            for incoming, target in ((selected, combined), (cr, combined_cohort)):
                for pid, run in incoming.items():
                    if pid not in globally_excluded:
                        target[pid] = longest([target[pid], run]) if pid in target else run
        rows.append({'name': 'Компания', **statistics_for(combined.values(), combined_cohort.values()),
                     'warnings': warnings, 'coverage': [m for m, s in snapshots.items() if s]})
    return {'status': 'ready', 'from': start.isoformat(), 'to': end.isoformat(), 'cohort': cohort,
            'mode': mode, 'rows': rows, 'notes': NOTES, 'partial': any(r['warnings'] for r in rows), 'loading': loading,
            'updated_at': min(s['updated_at'] for s in snapshots.values() if s),
            'metrics': [{'id': key, 'title': title, 'columns': columns} for key, title, columns in METRICS]}


def export_workbook(report):
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    workbook = Workbook()
    workbook.remove(workbook.active)
    for _, title, columns in METRICS:
        sheet = workbook.create_sheet(title)
        sheet.append([title + (' — компания' if report['mode'] == 'company' else ' — по объектам')])
        sheet.append([f"{report['from']} — {report['to']}; когорта {report['cohort']}"])
        sheet.append(['Неполные исходные данные' if report['partial'] else 'Сводки за период загружены'])
        sheet.append(['Объект' if report['mode'] == 'objects' else 'Компания', *[c[1] for c in columns], 'Предупреждения'])
        for row in report['rows']:
            sheet.append([row['name'], *[row[k] if row[k] is not None else 'Нет данных' for k, _ in columns], '; '.join(row['warnings'])])
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = 's'
                cell.alignment = Alignment(vertical='center', wrap_text=True)
                if cell.row == 4:
                    cell.fill = PatternFill('solid', fgColor='29475F')
                    cell.font = Font(color='FFFFFF', bold=True)
                elif cell.row >= 5 and cell.row % 2:
                    cell.fill = PatternFill('solid', fgColor='EEF3F7')
        for i, (key, _) in enumerate(columns, 2):
            for r in range(5, 5 + len(report['rows'])):
                sheet.cell(r, i).number_format = '0.0%' if key.endswith('_share') else ('0.00' if key in {'mean', 'trimmed', 'median', 'cohort_mean'} else '0')
        sheet.append([])
        for note in report['notes']:
            sheet.append([note])
        sheet.column_dimensions['A'].width = 40
        for i in range(2, len(columns) + 2):
            sheet.column_dimensions[get_column_letter(i)].width = 22
        sheet.column_dimensions[get_column_letter(len(columns) + 2)].width = 65
        sheet.freeze_panes = 'B5'
        sheet.sheet_view.showGridLines = False
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
