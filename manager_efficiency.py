# manager_efficiency.py
# -*- coding: utf-8 -*-
import csv
import io
from collections import defaultdict
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

SHORT_CALL_SECONDS = 15
ANALYTICS_EXCLUDED_NAME_PARTS = ['Без менеджера', 'Тарасов Максим']


def secfmt(seconds):
    seconds = int(seconds or 0)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f'{hours}:{minutes:02d}:{secs:02d}'


def pct(value):
    return f'{value:.0%}'


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
            'out_success': 0,
            'out_failed': 0,
            'line_seconds': 0,
            'short_calls': 0,
            'contacts': 0,
            'call_windows': []
        }
    )

    for row in rows:
        key = (row.get('system') or '', row.get('employee_name') or 'Без менеджера')
        item = stats[key]
        direction = row.get('direction')
        duration = int(row.get('clean_talk_duration') or 0)
        is_talked = bool(row.get('is_talked'))

        if direction == 'in':
            if is_talked and duration > 0:
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
                item['contacts'] += 1
                if duration < SHORT_CALL_SECONDS:
                    item['short_calls'] += 1
            else:
                item['out_failed'] += 1

    max_contacts = max((v['contacts'] for v in stats.values()), default=0) or 1
    max_line_seconds = max((v['line_seconds'] for v in stats.values()), default=0) or 1

    result = []
    for (system, manager), item in stats.items():
        out_total = item['out_success'] + item['out_failed']
        if item['contacts'] == 0 and out_total == 0:
            continue

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
            'out_success': item['out_success'],
            'out_failed': item['out_failed'],
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
            'index_text': f'{index:.1f}'
        })

    result.sort(key=lambda item: item['index'], reverse=True)
    return result


def save_rating_csv(rating):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        'Система', 'Менеджер', 'Вх прин', 'Исх усп', 'Исх неусп',
        'Время', 'Средн', 'Перерыв', '% дозв', '% кор', 'Индекс'
    ])
    for item in rating:
        writer.writerow([
            item['system'], item['manager'], item['in_accepted'], item['out_success'],
            item['out_failed'], item['line_time'], item['avg_time'], item['break_time'],
            item['out_success_rate_text'], item['short_share_text'], item['index_text']
        ])
    return '\ufeff' + output.getvalue()


def fonts():
    try:
        return {
            'title': ImageFont.truetype('arialbd.ttf', 18),
            'bold': ImageFont.truetype('arialbd.ttf', 14),
            'regular': ImageFont.truetype('arial.ttf', 14),
            'small': ImageFont.truetype('arial.ttf', 12)
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
    return any(part in item['manager'] for part in ANALYTICS_EXCLUDED_NAME_PARTS)


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
    headers = ['Система', 'Менеджер', 'Вх прин', 'Исх усп', 'Исх неусп', 'Время', 'Средн', 'Перерыв', '% дозв', '% кор', 'Индекс']
    widths = [86, 300, 70, 70, 80, 90, 75, 80, 70, 65, 70]
    row_h = 28
    top = 44
    note_h = 88
    width = sum(widths) + 2
    height = top + row_h * (len(rating) + 1) + note_h

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
        if index == 2:
            fill = colors['yellow']
        if index == 3:
            fill = colors['green']
        if index == 4:
            fill = colors['red']
        if index in (5, 6, 7, 8, 9, 10):
            fill = colors['neutral']
        draw.rectangle([x, y, x + widths[index], y + row_h], fill=fill, outline=colors['grid'])
        draw.text((x + 5, y + 7), header, fill=colors['text'], font=f['bold'])
        x += widths[index]

    for item in rating:
        y += row_h
        row = [
            item['system'], item['manager'], item['in_accepted'], item['out_success'],
            item['out_failed'], item['line_time'], item['avg_time'], item['break_time'],
            item['out_success_rate_text'], item['short_share_text'], item['index_text']
        ]
        x = 1
        for index, value in enumerate(row):
            fill = colors['white']
            if index == 2:
                fill = colors['yellow']
            if index == 3:
                fill = colors['green']
            if index == 4:
                fill = colors['red']
            if index == 6:
                fill = red_green_scale(item['avg_seconds'], min_avg, max_avg)
            if index == 7:
                fill = break_fill(item, min_break, max_break, colors)
            if index in (5, 8, 9, 10):
                fill = colors['neutral']
            draw.rectangle([x, y, x + widths[index], y + row_h], fill=fill, outline=colors['grid'])
            text = str(value)
            font = f['bold'] if index == 10 else f['regular']
            tx = x + 5 if index in (0, 1) else x + widths[index] - draw.textlength(text, font=font) - 6
            draw.text((tx, y + 7), text, fill=colors['text'], font=font)
            x += widths[index]

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
