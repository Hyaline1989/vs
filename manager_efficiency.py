# manager_efficiency.py
# -*- coding: utf-8 -*-
import csv
import io
import os
import re
from collections import defaultdict
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

SHORT_CALL_SECONDS = 15
ANALYTICS_EXCLUDED_NAME_PARTS = ['Без менеджера', 'Тарасов Максим']
EXCLUDED_MANAGER_PREFIXES = ['сервис', 'без менеджера']
EXCLUDED_MANAGER_NAME_PARTS = ['тройнов максим', 'тарасов максим', 'грибова надежда']


def is_excluded_manager(manager_name):
    manager_name = (manager_name or '').strip().casefold()
    manager_name = re.sub(r'^\([^)]*\)\s*', '', manager_name)
    return (
        any(manager_name.startswith(prefix) for prefix in EXCLUDED_MANAGER_PREFIXES)
        or any(name_part in manager_name for name_part in EXCLUDED_MANAGER_NAME_PARTS)
    )


def secfmt(seconds):
    seconds = int(seconds or 0)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f'{hours}:{minutes:02d}:{secs:02d}'


def pct(value):
    return f'{value:.0%}'


def decimal_comma(value):
    return f'{value:.1f}'.replace('.', ',')


def parse_dt(value):
    if not value:
        return None
    return datetime.strptime(value[:19], '%Y-%m-%d %H:%M:%S')


def average_break_seconds(call_windows):
    normalized = []
    seen = set()
    for start_raw, finish_raw, call_id in call_windows:
        if call_id in seen:
            continue
        seen.add(call_id)
        start = parse_dt(start_raw)
        finish = parse_dt(finish_raw)
        if start is None:
            continue
        if finish is None or finish < start:
            finish = start
        normalized.append((start, finish))

    normalized.sort(key=lambda item: item[0])
    breaks = []
    for previous, current in zip(normalized, normalized[1:]):
        gap = (current[0] - previous[1]).total_seconds()
        if gap > 0:
            breaks.append(gap)
    return sum(breaks) / len(breaks) if breaks else 0


def calculate_efficiency_rating(rows):
    stats = defaultdict(
        lambda: {
            'in_accepted': 0,
            'in_missed': 0,
            'company_unassigned': False,
            'out_success': 0,
            'out_over_30': 0,
            'out_over_15': 0,
            'out_failed': 0,
            'line_seconds': 0,
            'short_calls': 0,
            'contacts': 0,
            'call_windows': []
        }
    )

    for row in rows:
        category = row.get('incoming_category')
        if category in ('blocked_old', 'blocked_new', 'technical'):
            continue
        manager_name = row.get('employee_name') or 'Без менеджера'
        if is_excluded_manager(manager_name):
            continue
        if category == 'missed':
            item = stats[('', 'Потерянные звонки')]
            item['company_unassigned'] = True
            item['in_missed'] += 1
            continue

        # Защита также для ранее закэшированных строк нормализованных звонков.
        if (row.get('direction') == 'out'
                and int(row.get('clean_talk_duration') or 0) > 0
                and not row.get('is_talked')):
            continue

        key = (row.get('system') or '', manager_name)
        item = stats[key]
        item['company_unassigned'] = item['company_unassigned'] or row.get('company_unassigned', False)
        direction = row.get('direction')
        duration = int(row.get('clean_talk_duration') or 0)
        is_talked = bool(row.get('is_talked'))

        if direction == 'in':
            if category == 'missed':
                item['in_missed'] += 1
                continue
            if (is_talked and duration > 0) or category == 'accepted':
                item['in_accepted'] += 1
                item['contacts'] += 1
                item['line_seconds'] += duration
                item['call_windows'].append((row.get('start_time'), row.get('finish_time'), row.get('id')))
                if duration < SHORT_CALL_SECONDS:
                    item['short_calls'] += 1
            continue

        if direction == 'out':
            item['line_seconds'] += duration
            item['call_windows'].append((row.get('start_time'), row.get('finish_time'), row.get('id')))
            if duration > 0:
                item['out_success'] += 1
                if duration > 15:
                    item['out_over_15'] += 1
                if duration > 30:
                    item['out_over_30'] += 1
                item['contacts'] += 1
                if duration < SHORT_CALL_SECONDS:
                    item['short_calls'] += 1
            else:
                item['out_failed'] += 1

    max_contacts = max((v['contacts'] for v in stats.values() if not v['company_unassigned']), default=0) or 1
    max_line_seconds = max((v['line_seconds'] for v in stats.values() if not v['company_unassigned']), default=0) or 1

    result = []
    for (system, manager), item in stats.items():
        out_total = item['out_success'] + item['out_failed']
        if item['contacts'] == 0 and out_total == 0 and not item['in_missed']:
            continue

        total_calls = item['in_missed'] + item['in_accepted'] + item['out_success'] + item['out_failed']
        out_success_rate = item['out_success'] / out_total if out_total else 0
        short_share = item['short_calls'] / item['contacts'] if item['contacts'] else 0
        avg_seconds = item['line_seconds'] / item['contacts'] if item['contacts'] else 0
        break_seconds = average_break_seconds(item['call_windows'])

        contact_score = item['contacts'] / max_contacts * 45
        line_score = item['line_seconds'] / max_line_seconds * 25
        quality_score = out_success_rate * 25
        penalty = short_share * 15 + item['out_failed'] * 0.05
        index = max(0, min(100, contact_score + line_score + quality_score - penalty))

        result.append({
            'system': system,
            'manager': manager,
            'in_accepted': item['in_accepted'],
            'in_missed': item['in_missed'],
            'company_unassigned': item['company_unassigned'],
            'out_success': item['out_success'],
            'out_over_30': item['out_over_30'],
            'out_over_15': item['out_over_15'],
            'lost_row': manager == 'Потерянные звонки',
            'out_failed': item['out_failed'],
            'total_calls': total_calls,
            'line_seconds': item['line_seconds'],
            'avg_seconds': avg_seconds,
            'break_seconds': break_seconds,
            'out_success_rate': out_success_rate,
            'short_share': short_share,
            'index': index,
            'line_time': secfmt(item['line_seconds']),
            'avg_time': secfmt(avg_seconds),
            'break_time': secfmt(break_seconds),
            'out_success_rate_text': pct(out_success_rate),
            'short_share_text': pct(short_share),
            'index_text': '' if item['company_unassigned'] else f'{index:.1f}'
        })

    result.sort(key=lambda item: item['index'], reverse=True)
    return result


def rating_totals(rating):
    """Итоги отображаемых строк; средние — среднее показателей менеджеров."""
    result = {'system': '', 'manager': 'Итого', 'short_share_text': '', 'index_text': ''}
    for key in ('in_missed', 'in_accepted', 'out_success', 'out_over_30', 'out_over_15', 'out_failed', 'total_calls', 'line_seconds'):
        result[key] = sum(item.get(key, 0) for item in rating)
    managers = [item for item in rating if not item.get('company_unassigned')]
    for key in ('avg_seconds', 'break_seconds'):
        result[key] = sum(item[key] for item in managers) / len(managers) if managers else 0
    outgoing = result['out_success'] + result['out_failed']
    result['out_success_rate'] = result['out_success'] / outgoing if outgoing else 0
    result['out_success_rate_text'] = pct(result['out_success_rate'])
    for label, key in (('line_time','line_seconds'), ('avg_time','avg_seconds'), ('break_time','break_seconds')):
        result[label] = secfmt(result[key])
    return result


def save_rating_csv(rating):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        'Система', 'Менеджер', 'Исх усп >15 сек', 'Исх усп >30 сек', 'Вх неприн', 'Вх прин', 'Исх усп', 'Исх неусп', 'Итого',
        'Время', 'Средн', 'Перерыв', '% дозв', '% кор', 'Индекс'
    ])
    for item in [*rating, rating_totals(rating)]:
        writer.writerow([
            item['system'], item['manager'], item.get('out_over_15', 0), item.get('out_over_30', 0), item.get('in_missed', 0) if item.get('lost_row') or 'index' not in item else '', item['in_accepted'], item['out_success'],
            item['out_failed'], item['total_calls'], item['line_time'], item['avg_time'], item['break_time'],
            item['out_success_rate_text'], item['short_share_text'], decimal_comma(item['index']) if 'index' in item and not item.get('company_unassigned') else ''
        ])
    return '\ufeff' + output.getvalue()


def find_font(*filenames):
    font_dirs = [
        '',
        '/usr/share/fonts/truetype/dejavu',
        '/usr/share/fonts/truetype/liberation',
        '/usr/share/fonts/truetype/liberation2',
        '/usr/share/fonts/opentype/noto',
        '/usr/share/fonts/truetype/noto',
        'C:/Windows/Fonts'
    ]
    for directory in font_dirs:
        for filename in filenames:
            path = os.path.join(directory, filename) if directory else filename
            if os.path.exists(path):
                return path
    return filenames[0]


def fonts():
    try:
        regular = find_font('arial.ttf', 'DejaVuSans.ttf', 'LiberationSans-Regular.ttf', 'NotoSans-Regular.ttf')
        bold = find_font('arialbd.ttf', 'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf', 'NotoSans-Bold.ttf')
        return {
            'title': ImageFont.truetype(bold, 18),
            'bold': ImageFont.truetype(bold, 14),
            'regular': ImageFont.truetype(regular, 14),
            'small': ImageFont.truetype(regular, 12)
        }
    except OSError:
        font = ImageFont.load_default()
        return {'title': font, 'bold': font, 'regular': font, 'small': font}


def red_green_scale(value, min_value, max_value):
    if max_value <= min_value:
        ratio = 0.5
    else:
        ratio = (value - min_value) / (max_value - min_value)
    ratio = max(0, min(1, ratio))
    low = (248, 203, 173)
    mid = (255, 242, 204)
    high = (198, 239, 206)
    if ratio < 0.5:
        local = ratio * 2
        return tuple(round(low[i] + (mid[i] - low[i]) * local) for i in range(3))
    local = (ratio - 0.5) * 2
    return tuple(round(mid[i] + (high[i] - mid[i]) * local) for i in range(3))


def green_red_scale(value, min_value, max_value):
    if max_value <= min_value:
        ratio = 0.5
    else:
        ratio = (value - min_value) / (max_value - min_value)
    ratio = max(0, min(1, ratio))
    low = (198, 239, 206)
    mid = (255, 242, 204)
    high = (248, 203, 173)
    if ratio < 0.5:
        local = ratio * 2
        return tuple(round(low[i] + (mid[i] - low[i]) * local) for i in range(3))
    local = (ratio - 0.5) * 2
    return tuple(round(mid[i] + (high[i] - mid[i]) * local) for i in range(3))


def rgb_to_hex(rgb):
    return '#{:02x}{:02x}{:02x}'.format(*rgb)


def is_excluded_from_break_scale(item):
    return item.get('company_unassigned', False) or any(part in item['manager'] for part in ANALYTICS_EXCLUDED_NAME_PARTS)


def break_scale_bounds(rating):
    values = sorted(
        item['break_seconds']
        for item in rating
        if item['break_seconds'] > 0 and not is_excluded_from_break_scale(item)
    )
    if not values:
        return 0, 0
    if len(values) < 4:
        return values[0], values[-1]
    trim_count = max(1, int(len(values) * 0.1))
    trimmed = values[:-trim_count] if len(values) - trim_count >= 3 else values
    return trimmed[0], trimmed[-1]


def break_fill(item, min_break, max_break, colors):
    if item['break_seconds'] <= 0 or is_excluded_from_break_scale(item):
        return colors['neutral']
    if max_break > min_break and item['break_seconds'] > max_break:
        return colors['strong_red']
    return green_red_scale(item['break_seconds'], min_break, max_break)


def add_display_colors(rating):
    colors = {
        'strong_red': (244, 176, 132),
        'neutral': (242, 242, 242)
    }
    min_break, max_break = break_scale_bounds(rating)
    for item in rating:
        item['break_fill'] = rgb_to_hex(break_fill(item, min_break, max_break, colors))
    return rating


def build_rating_png(rating, date_ru):
    f = fonts()
    headers = ['Система', 'Менеджер', 'Исх усп >15 сек', 'Исх усп >30 сек', 'Вх неприн', 'Вх прин', 'Исх усп', 'Исх неусп', 'Итого', 'Время', 'Средн', 'Перерыв', '% дозв', '% кор', 'Индекс']
    widths = [86, 300] + [135] * 13
    row_h = 28
    top = 44
    note_h = 88
    width = sum(widths) + 2
    height = top + row_h * (len(rating) + 2) + note_h

    colors = {
        'header': (221, 231, 242),
        'yellow': (255, 255, 0),
        'green': (146, 208, 80),
        'red': (248, 203, 203),
        'strong_red': (244, 176, 132),
        'neutral': (242, 242, 242),
        'white': (255, 255, 255),
        'grid': (180, 180, 180),
        'text': (20, 20, 20)
    }
    avg_values = [item['avg_seconds'] for item in rating]
    min_avg = min(avg_values, default=0)
    max_avg = max(avg_values, default=0)
    min_break, max_break = break_scale_bounds(rating)

    image = Image.new('RGB', (width, height), colors['white'])
    draw = ImageDraw.Draw(image)
    draw.text((6, 10), f'Общий рейтинг эффективности менеджеров за {date_ru}', fill=colors['text'], font=f['title'])

    y = top
    x = 1
    for index, header in enumerate(headers):
        fill = colors['header']
        if header == 'Вх прин':
            fill = colors['yellow']
        if header == 'Исх усп':
            fill = colors['green']
        if header in ('Вх неприн', 'Исх неусп'):
            fill = colors['red']
        if index >= 8:
            fill = colors['neutral']
        draw.rectangle([x, y, x + widths[index], y + row_h], fill=fill, outline=colors['grid'])
        draw.text((x + 5, y + 7), header, fill=colors['text'], font=f['bold'])
        x += widths[index]

    for row_index, item in enumerate([*rating, rating_totals(rating)]):
        y += row_h
        row = [
            item['system'], item['manager'], item.get('out_over_15', 0), item.get('out_over_30', 0), item.get('in_missed', 0) if item.get('lost_row') or 'index' not in item else '', item['in_accepted'], item['out_success'],
            item['out_failed'], item['total_calls'], item['line_time'], item['avg_time'], item['break_time'],
            item['out_success_rate_text'], item['short_share_text'], item['index_text']
        ]
        x = 1
        for index, value in enumerate(row):
            fill = (240, 246, 255) if row_index % 2 else colors['white']
            if headers[index] == 'Вх прин':
                fill = colors['yellow']
            if headers[index] == 'Исх усп':
                fill = colors['green']
            if headers[index] in ('Вх неприн', 'Исх неусп'):
                fill = colors['red']
            if headers[index] == 'Средн':
                fill = red_green_scale(item['avg_seconds'], min_avg, max_avg)
            if headers[index] == 'Перерыв':
                fill = break_fill(item, min_break, max_break, colors)
            if headers[index] in ('Итого', 'Время', '% дозв', '% кор', 'Индекс'):
                fill = colors['neutral']
            if 'index' not in item:
                fill = colors['header']
            draw.rectangle([x, y, x + widths[index], y + row_h], fill=fill, outline=colors['grid'])
            text = str(value)
            font = f['bold'] if headers[index] == 'Индекс' or 'index' not in item else f['regular']
            tx = x + 5 if index in (0, 1) else x + widths[index] - draw.textlength(text, font=font) - 6
            draw.text((tx, y + 7), text, fill=colors['text'], font=font)
            x += widths[index]

    # Outline the two additional metrics without colouring their cells.
    x = 1 + sum(widths[:2])
    for column in (2, 3):
        draw.rectangle([x, top, x + widths[column], y + row_h], outline=(0, 0, 0), width=2)
        x += widths[column]
    y += row_h + 8
    notes = [
        'Индекс: контакты 45%, время на линии 25%, успешность исходящих 25%, понижение за короткие разговоры',
        'и за исходящие попытки, которые не привели к разговору.',
        f'Короткий разговор: меньше {SHORT_CALL_SECONDS} секунд. Перерыв: меньше — зеленее, больше — краснее.',
        'Шкала перерывов строится по рабочим менеджерам; тестовые/без менеджера не растягивают диапазон.'
    ]
    for note in notes:
        draw.text((6, y), note, fill=(80, 80, 80), font=f['small'])
        y += 20

    output = io.BytesIO()
    image.save(output, format='PNG')
    output.seek(0)
    return output
