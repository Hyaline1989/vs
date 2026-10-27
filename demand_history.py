"""Постоянный архив последней сохранённой потребности за день. Без автозапуска."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from contextlib import closing
import sqlite3
from normalizer import ObjectNameNormalizer

SCHEMA = '''CREATE TABLE IF NOT EXISTS demand_history (
    day TEXT NOT NULL, object_name TEXT NOT NULL,
    count INTEGER NOT NULL CHECK(count >= 0), saved_at TEXT NOT NULL,
    PRIMARY KEY(day, object_name)
)'''


def record_current(conn, object_name=None, now=None, extra_names=()):
    """Вызывается ВНУТРИ транзакции сохранения потребности, не делает commit."""
    now = now or datetime.now(timezone(timedelta(hours=3)))
    day, stamp = now.date().isoformat(), now.isoformat(timespec='seconds')
    query = '''SELECT object_name, SUM(COALESCE(rf_men,0)+COALESCE(rf_women,0)+
        COALESCE(rf_family,0)+COALESCE(cis_men,0)+COALESCE(cis_women,0)+COALESCE(cis_family,0))
        FROM current_requirements'''
    args = ()
    if object_name is not None:
        query += ' WHERE object_name = ?'
        args = (object_name,)
    totals = dict(conn.execute(query + ' GROUP BY object_name', args).fetchall())
    for name in extra_names:
        totals.setdefault(name, 0)
    for name, count in totals.items():
        if not isinstance(count, int) or count < 0:
            raise ValueError('Потребность должна быть целым неотрицательным числом')
        conn.execute('''INSERT INTO demand_history(day,object_name,count,saved_at) VALUES(?,?,?,?)
            ON CONFLICT(day,object_name) DO UPDATE SET count=excluded.count,saved_at=excluded.saved_at''',
            (day, name, count, stamp))
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='demand_history_legacy' AND type='table'").fetchone():
            conn.execute('DELETE FROM demand_history_legacy WHERE day=? AND object_name=?', (day, name))


def report_from_connection(conn, start, end):
    if start > end or (end-start).days > 365:
        raise ValueError('Выберите период не более 366 дней')
    dates = [(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
    records = conn.execute('SELECT day,object_name,count,saved_at FROM demand_history WHERE day BETWEEN ? AND ?',
                           (dates[0], dates[-1])).fetchall()
    priorities = conn.execute('''SELECT date,object_name,MAX(is_high) FROM daily_snapshots
        WHERE date BETWEEN ? AND ? GROUP BY date,object_name''', (dates[0], dates[-1])).fetchall()
    normalize = ObjectNameNormalizer().normalize
    priority_days, flags = set(), set()
    for day, name, high in priorities:
        priority_days.add(day)
        if high:
            flags.add((day, normalize(name)))
    names = sorted({r[1] for r in records}, key=str.casefold)
    values = {(day,name):count for day,name,count,_ in records}
    legacy = set()
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='demand_history_legacy' AND type='table'").fetchone():
        legacy = set(conn.execute('SELECT day,object_name FROM demand_history_legacy WHERE day BETWEEN ? AND ?', (dates[0], dates[-1])))
    objects = [{'name':name, 'counts':[values.get((day,name)) for day in dates],
                'legacy':[(day,name) in legacy for day in dates],
                'priorities':[(day,normalize(name)) in flags if day in priority_days else None for day in dates]}
               for name in names]
    totals, incomplete = [], []
    for i in range(len(dates)):
        counts = [o['counts'][i] for o in objects]
        present = [v for v in counts if v is not None]
        totals.append(sum(present) if present else None)
        incomplete.append(not counts or len(present) != len(counts))
    return {'dates':dates, 'objects':objects, 'totals':totals, 'incomplete':incomplete,
            'priority_saved':[day in priority_days for day in dates],
            'last_saved_at':max((r[3] for r in records), default=None)}


def report_for_period(database, start, end):
    uri = Path(database).resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        return report_from_connection(conn, start, end)
