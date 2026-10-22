"""Ставки на дату направления. Только явное сохранение, без записей при чтении."""
import calendar
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from datetime import date, timedelta, datetime, timezone
from normalizer import ObjectNameNormalizer


class RatesConflict(ValueError):
    pass


def create_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS candidate_rates (
        object_id INTEGER NOT NULL, day TEXT NOT NULL,
        amount INTEGER NOT NULL CHECK(amount >= 0), source TEXT NOT NULL,
        comment TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(object_id, day))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS candidate_rate_history (
        id INTEGER PRIMARY KEY, object_id INTEGER NOT NULL, object_name TEXT NOT NULL,
        day TEXT NOT NULL, old_amount INTEGER, new_amount INTEGER NOT NULL,
        old_source TEXT, new_source TEXT NOT NULL, old_comment TEXT,
        new_comment TEXT NOT NULL, actor_id INTEGER NOT NULL,
        actor_name TEXT NOT NULL, changed_at TEXT NOT NULL)''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_rate_history_day ON candidate_rate_history(day, object_id)')


def period(start, end):
    if not all(isinstance(v, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', v) for v in (start, end)):
        raise ValueError('Укажите даты С и По')
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if not 0 <= (last - first).days <= 365:
        raise ValueError('Период должен быть от 1 до 366 дней')
    return [(first + timedelta(days=i)).isoformat() for i in range((last-first).days+1)]


def _cells(conn, object_id, days):
    row = conn.execute('SELECT name FROM objects_settings WHERE id=?', (object_id,)).fetchone()
    if not row:
        raise ValueError('Объект не найден')
    name = row[0]
    normalize = ObjectNameNormalizer().normalize
    key = normalize(name)
    collisions = sum(normalize(r[0]) == key for r in conn.execute('SELECT name FROM objects_settings'))
    priorities = {}
    if collisions == 1:
        for day, obj, high in conn.execute('SELECT date, object_name, MAX(is_high) FROM daily_snapshots WHERE date BETWEEN ? AND ? GROUP BY date, object_name', (days[0], days[-1])):
            if normalize(obj) == key:
                priorities[day] = priorities.get(day, False) or bool(high)
    stored = {r[0]: r[1:] for r in conn.execute('SELECT day, amount, source, comment, updated_at FROM candidate_rates WHERE object_id=? AND day BETWEEN ? AND ?', (object_id, days[0], days[-1]))}
    cells = []
    for day in days:
        saved = stored.get(day)
        suggestion = (4000 if priorities[day] else 2500) if day in priorities else None
        cells.append(dict(day=day, amount=saved[0] if saved else None,
                          source=saved[1] if saved else None, comment=saved[2] if saved else '',
                          updated_at=saved[3] if saved else None, suggestion=suggestion))
    return name, cells


def _revision(cells):
    return hashlib.sha256(json.dumps(cells, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def preview(conn, object_id, start, end):
    days = period(start, end)
    name, cells = _cells(conn, object_id, days)
    return dict(object_id=object_id, name=name, cells=cells, revision=_revision(cells))


def read_calendar(path, month):
    if not isinstance(month, str) or not re.fullmatch(r'\d{4}-\d{2}', month):
        raise ValueError('Выберите месяц')
    first = date.fromisoformat(month + '-01')
    end = date(first.year, first.month, calendar.monthrange(first.year, first.month)[1]).isoformat()
    with closing(sqlite3.connect(path)) as conn:
        conn.execute('BEGIN')
        objects = list(conn.execute('SELECT id, name FROM objects_settings'))
        rows = [preview(conn, oid, first.isoformat(), end) for oid, _ in sorted(objects, key=lambda r: r[1].casefold())]
        return dict(days=period(first.isoformat(), end), rows=rows)


def read_preview(path, object_id, start, end):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute('BEGIN')
        return preview(conn, object_id, start, end)


def save_rates(path, payload, actor_id, actor_name):
    oid = payload.get('object_id')
    if type(oid) is not int:
        raise ValueError('Выберите объект')
    mode = payload.get('mode')
    amount = payload.get('amount')
    comment = payload.get('comment', '')
    if mode not in ('manual', 'confirm'):
        raise ValueError('Неизвестное действие')
    if not isinstance(comment, str) or len(comment) > 500:
        raise ValueError('Комментарий — не более 500 символов')
    if mode == 'manual' and (type(amount) is not int or not 0 <= amount <= 1000000):
        raise ValueError('Сумма — целое число от 0 до 1 000 000 рублей')
    if mode == 'manual' and not comment.strip():
        raise ValueError('Укажите причину ручной ставки или название акции')
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        data = preview(conn, oid, payload.get('from'), payload.get('to'))
        if payload.get('revision') != data['revision']:
            raise RatesConflict('Данные изменились. Посмотрите обновлённый расчёт и подтвердите снова.')
        changes = []
        for cell in data['cells']:
            if mode == 'confirm' and (cell['amount'] is not None or cell['suggestion'] is None):
                continue
            value = amount if mode == 'manual' else cell['suggestion']
            source = 'manual' if mode == 'manual' else 'priority'
            note = comment.strip() if mode == 'manual' else 'Подтверждено по сохранённым приоритетам'
            if (cell['amount'], cell['source'], cell['comment']) == (value, source, note):
                continue
            changes.append((cell, value, source, note))
        now = datetime.now(timezone.utc).isoformat()
        for cell, value, source, note in changes:
            conn.execute('''INSERT INTO candidate_rate_history
                (object_id,object_name,day,old_amount,new_amount,old_source,new_source,old_comment,new_comment,actor_id,actor_name,changed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (oid,data['name'],cell['day'],cell['amount'],value,cell['source'],source,cell['comment'],note,actor_id,actor_name,now))
            conn.execute('''INSERT INTO candidate_rates VALUES (?,?,?,?,?,?)
                ON CONFLICT(object_id,day) DO UPDATE SET amount=excluded.amount,source=excluded.source,
                comment=excluded.comment,updated_at=excluded.updated_at''', (oid,cell['day'],value,source,note,now))
        return dict(changed=len(changes), skipped=len(data['cells'])-len(changes))


def read_history(path, object_id, start, end):
    period(start, end)
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute('''SELECT * FROM candidate_rate_history
            WHERE object_id=? AND day BETWEEN ? AND ? ORDER BY id DESC''', (object_id, start, end))]


def sync_priority_rates(conn, day=None, actor_id=0, actor_name='Автоматически по приоритетам'):
    """В транзакции вызывающего кода; ручные и неизвестные источники не меняем."""
    normalize = ObjectNameNormalizer().normalize
    objects = {}
    for oid, name in conn.execute('SELECT id, name FROM objects_settings'):
        objects.setdefault(normalize(name), []).append((oid, name))
    query = 'SELECT date, object_name, MAX(is_high) FROM daily_snapshots'
    rows = conn.execute(query + (' WHERE date=?' if day else '') + ' GROUP BY date, object_name', (day,) if day else ())
    priorities = {}
    for date_key, name, high in rows:
        key = (date_key, normalize(name))
        priorities[key] = priorities.get(key, False) or bool(high)
    changed = 0
    now = datetime.now(timezone.utc).isoformat()
    for (date_key, key), high in priorities.items():
        matches = objects.get(key, [])
        if len(matches) != 1:
            continue
        oid, name = matches[0]
        old = conn.execute('SELECT amount, source, comment FROM candidate_rates WHERE object_id=? AND day=?', (oid, date_key)).fetchone()
        amount = 4000 if high else 2500
        if old and (old[1] != 'priority' or old[0] == amount):
            continue
        note = 'Автоматически по зафиксированным приоритетам'
        conn.execute('''INSERT INTO candidate_rate_history
            (object_id,object_name,day,old_amount,new_amount,old_source,new_source,old_comment,new_comment,actor_id,actor_name,changed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (oid,name,date_key,old[0] if old else None,amount,old[1] if old else None,'priority',old[2] if old else '',note,actor_id,actor_name,now))
        conn.execute('''INSERT INTO candidate_rates VALUES (?,?,?,?,?,?)
            ON CONFLICT(object_id,day) DO UPDATE SET amount=excluded.amount,source=excluded.source,
            comment=excluded.comment,updated_at=excluded.updated_at''', (oid,date_key,amount,'priority',note,now))
        changed += 1
    return changed
