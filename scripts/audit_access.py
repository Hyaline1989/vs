"""Read-only access inventory. Does not import the application or modify the DB."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3

MODULES = ('dashboard', 'selection', 'worker_status', 'reports', 'admin')
LABELS = ('Дашборд', 'Подбор объектов', 'Вахтовики', 'Отчёты', 'Админ-панель')


def audit(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {'users', 'objects_settings', 'user_module_permissions', 'user_object_permissions'}
    if required - tables:
        raise ValueError('Не найдены таблицы: ' + ', '.join(sorted(required - tables)))
    if ('access_memberships' in tables) != ('access_departments' in tables):
        raise ValueError('Неполная структура таблиц отделов. Проверка остановлена.')
    objects = [r[0] for r in conn.execute('SELECT id FROM objects_settings ORDER BY id')]
    departments = {}
    memberships = {}
    if 'access_memberships' in tables:
        departments = {r[0]: (r[1], json.loads(r[2])) for r in conn.execute('SELECT id,name,policy FROM access_departments')}
        memberships = {r[0]: (r[1], json.loads(r[2])) for r in conn.execute('SELECT user_id,department_id,overrides FROM access_memberships')}
    result = []
    for uid, name, role, active in conn.execute('SELECT id,full_name,role,is_active FROM users ORDER BY id'):
        legacy_modules = dict(conn.execute('SELECT module_name,can_view FROM user_module_permissions WHERE user_id=?', (uid,)))
        legacy_objects = {r[0]: (bool(r[1]), bool(r[2])) for r in conn.execute('SELECT object_id,can_view_dashboard,can_view_selection FROM user_object_permissions WHERE user_id=?', (uid,))}
        membership = memberships.get(uid)
        department_name = None
        warning = None
        if membership:
            did, override = membership
            department_name, policy = departments.get(did, (None, {}))
            if did is not None and did not in departments:
                warning = 'Назначен несуществующий отдел'
            modules = {key: bool(override.get('modules', {}).get(key, policy.get('modules', {}).get(key, False))) for key in MODULES}
            permissions = {oid: (bool(override.get('dashboard_objects', {}).get(str(oid), True)),
                                 bool(override.get('objects', {}).get(str(oid), policy.get('objects', {}).get(str(oid), policy.get('all_objects', False))))) for oid in objects}
            source = 'Отдел и исключения' if did is not None else 'Без отдела — новая система'
            exceptions = len(override.get('modules', {})) + len(override.get('objects', {})) + len(override.get('dashboard_objects', {}))
        else:
            modules = {key: bool(legacy_modules.get(key, False)) for key in MODULES}
            modules['admin'] = role == 'manager'
            permissions = {oid: legacy_objects.get(oid, (False, False)) for oid in objects}
            source, exceptions = 'Старые индивидуальные права', 0
        if role == 'admin':
            modules = dict.fromkeys(MODULES, True)
            permissions = dict.fromkeys(objects, (True, True))
            source = 'Полный доступ администратора'
        effective = {'role': role, 'active': bool(active), 'modules': modules,
                     'objects': {str(oid): {'dashboard': bool(modules['dashboard'] and flags[0]),
                                           'selection': bool(modules['selection'] and flags[1])}
                                 for oid, flags in permissions.items()}}
        digest = hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest()
        result.append(dict(id=uid, name=name or '(без имени)', source=source,
                           department=department_name, exceptions=exceptions,
                           warning=warning, fingerprint=digest, **effective))
    return {'object_count': len(objects), 'department_count': len(departments), 'users': result}


def main():
    parser = argparse.ArgumentParser(description='Проверка доступов Вектора только для чтения')
    parser.add_argument('--database', required=True)
    parser.add_argument('--json', action='store_true', help='Подробный снимок прав в stdout, без паролей и ключей')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')  # Все SELECT видят один согласованный снимок.
        report = audit(conn)
        conn.rollback()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print('ПРОВЕРКА ТОЛЬКО ДЛЯ ЧТЕНИЯ. Права и база не изменялись.')
    print(f"Пользователей: {len(report['users'])}; отделов: {report['department_count']}; объектов: {report['object_count']}")
    for source, count in Counter(u['source'] for u in report['users']).items():
        print(f'{source}: {count}')
    for user in report['users']:
        allowed = ', '.join(label for key, label in zip(MODULES, LABELS) if user['modules'][key]) or 'нет'
        count = sum(p['selection'] for p in user['objects'].values())
        print(f"\nID {user['id']} | {user['name']} | {user['role']} | {'активен' if user['active'] else 'заблокирован'}")
        print(f"  {user['source']}; отдел: {user['department'] or 'нет'}; явных настроек: {user['exceptions']}")
        print(f'  Разделы: {allowed}; доступных объектов подбора: {count}')
        print(f"  Отпечаток прав: {user['fingerprint']}")
        if user['warning']:
            print('  ВНИМАНИЕ: ' + user['warning'])
    print('\nСнимок отражает текущие разделы и объекты, а не права на будущие объекты. Заблокированные аккаунты показаны для инвентаризации.')


if __name__ == '__main__':
    main()
