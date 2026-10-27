"""Только чтение: предварительная проверка переноса старой потребности."""
import argparse
from collections import defaultdict
from contextlib import closing
from datetime import date
from pathlib import Path
import sqlite3


def preview(conn, start=None, end=None):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {'vacancy_requirements', 'vacancy_positions', 'vacancy_objects'}
    if not required <= tables:
        raise ValueError('Не найдены таблицы старой потребности')
    existing = set(conn.execute('SELECT day,object_name FROM demand_history')) if 'demand_history' in tables else set()
    rows = conn.execute('''SELECT vr.date, vo.name,
        SUM(COALESCE(vr.rf_men,0)+COALESCE(vr.rf_women,0)+COALESCE(vr.rf_family,0)
            +COALESCE(vr.cis_men,0)+COALESCE(vr.cis_women,0)+COALESCE(vr.cis_family,0))
        FROM vacancy_requirements vr
        JOIN vacancy_positions vp ON vp.id=vr.position_id
        JOIN vacancy_objects vo ON vo.id=vp.object_id
        GROUP BY vr.date,vo.name ORDER BY vr.date,vo.name''').fetchall()
    result = []
    for day, name, count in rows:
        parsed = date.fromisoformat(day)
        if (start and parsed < start) or (end and parsed > end):
            continue
        if not isinstance(count, int) or count < 0:
            raise ValueError(f'Некорректная потребность: {day}, {name}')
        result.append((day, name, count, (day, name) in existing))
    orphaned = conn.execute('''SELECT COUNT(*) FROM vacancy_requirements vr
        LEFT JOIN vacancy_positions vp ON vp.id=vr.position_id
        LEFT JOIN vacancy_objects vo ON vo.id=vp.object_id
        WHERE vo.id IS NULL''').fetchone()[0]
    return result, orphaned


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--from', dest='start', type=date.fromisoformat)
    parser.add_argument('--to', dest='end', type=date.fromisoformat)
    parser.add_argument('--details', action='store_true')
    args = parser.parse_args()
    if args.start and args.end and args.start > args.end:
        parser.error('Начало периода позже окончания')
    path = Path(args.database).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')
        rows, orphaned = preview(conn, args.start, args.end)
    print('ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР. База не изменена.')
    print('Источник: старые значения потребности, НЕ последняя потребность дня.')
    print('Дата | Объектов | К переносу | Уже в архиве (пропустить) | Сумма к переносу')
    days = defaultdict(list)
    for row in rows:
        days[row[0]].append(row)
    for day, items in sorted(days.items()):
        pending = [r for r in items if not r[3]]
        print(f'{day} | {len(items)} | {len(pending)} | {len(items)-len(pending)} | {sum(r[2] for r in pending)}')
    print('Всего записей к переносу:', sum(not r[3] for r in rows))
    print('Уже в архиве, останутся без изменений:', sum(r[3] for r in rows))
    print('Строк без доступного объекта во всей старой таблице:', orphaned)
    if not rows:
        print('Сохранившихся данных за выбранный период нет.')
    if args.details:
        for day, name, count, exists in rows:
            print(f'{day} | {name} | {count} | {"пропустить" if exists else "к переносу"}')
    print('Отсутствующие даты и объекты не будут заменяться нулями.')


if __name__ == '__main__':
    main()
