"""Department policy storage. No schema changes on import or application startup."""
import json
import sqlite3
from contextlib import closing

MODULES = ('dashboard', 'selection', 'worker_status', 'reports', 'admin')


def ready(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='access_memberships'").fetchone() is not None


def migrate(conn):
    """Explicit migration; existing permissions remain untouched."""
    conn.execute('CREATE TABLE IF NOT EXISTS access_departments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE COLLATE NOCASE, policy TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS access_memberships (user_id INTEGER PRIMARY KEY, department_id INTEGER, overrides TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE, FOREIGN KEY(department_id) REFERENCES access_departments(id))')


def validate_policy(value, override=False):
    if not isinstance(value, dict):
        raise ValueError('Неверный формат прав')
    modules, objects = value.get('modules', {}), value.get('objects', {})
    if not isinstance(modules, dict) or not isinstance(objects, dict):
        raise ValueError('Неверный формат прав')
    if any(k not in MODULES or type(v) is not bool for k, v in modules.items()):
        raise ValueError('Неверные права разделов')
    if any(not str(k).isdigit() or type(v) is not bool for k, v in objects.items()):
        raise ValueError('Неверные права объектов')
    result = {'modules': dict(modules), 'objects': {str(int(k)): v for k, v in objects.items()}}
    if not override:
        if type(value.get('all_objects', False)) is not bool:
            raise ValueError('Неверный режим объектов')
        result['all_objects'] = value.get('all_objects', False)
    return result


def effective(conn, user_id):
    """None means legacy user; otherwise return complete effective permissions."""
    if not ready(conn):
        return None
    row = conn.execute('SELECT m.overrides, d.policy FROM access_memberships m LEFT JOIN access_departments d ON d.id=m.department_id WHERE m.user_id=?', (user_id,)).fetchone()
    if row is None:
        return None
    override, department = json.loads(row[0]), json.loads(row[1] or '{}')
    modules = {key: bool(department.get('modules', {}).get(key, False)) for key in MODULES}
    modules.update(override.get('modules', {}))
    objects = {}
    for (oid,) in conn.execute('SELECT id FROM objects_settings'):
        key = str(oid)
        allow = department.get('objects', {}).get(key, department.get('all_objects', False))
        allow = override.get('objects', {}).get(key, allow)
        objects[oid] = {'selection': bool(allow), 'dashboard': True}
    return modules, objects


def get_effective(user_id):
    from database.db_core import DB_NAME
    with closing(sqlite3.connect(DB_NAME)) as conn:
        return effective(conn, user_id)


def assign(conn, user_ids, department_id, mode):
    if mode not in ('preserve', 'inherit'):
        raise ValueError('Выберите сохранить права или применить права отдела')
    if department_id is not None and not conn.execute('SELECT 1 FROM access_departments WHERE id=?', (department_id,)).fetchone():
        raise ValueError('Отдел не найден')
    if not isinstance(user_ids, list) or not user_ids or any(type(i) is not int for i in user_ids):
        raise ValueError('Выберите сотрудников')
    # Validate the entire batch before changing anything.
    for uid in user_ids:
        row = conn.execute('SELECT role FROM users WHERE id=?', (uid,)).fetchone()
        if not row or row[0] == 'admin':
            raise ValueError('Администраторы сохраняют полный доступ; выберите сотрудников других ролей')
    for uid in set(user_ids):
        overrides = {'modules': {}, 'objects': {}}
        if mode == 'preserve':
            current = effective(conn, uid)
            if current is None:
                role = conn.execute('SELECT role FROM users WHERE id=?', (uid,)).fetchone()[0]
                modules = dict(conn.execute('SELECT module_name, can_view FROM user_module_permissions WHERE user_id=?', (uid,)))
                modules = {m: bool(modules.get(m, False)) for m in MODULES}
                modules['admin'] = role == 'manager'
                objects = dict(conn.execute('SELECT object_id, can_view_selection FROM user_object_permissions WHERE user_id=?', (uid,)))
                overrides = {'modules': modules, 'objects': {str(oid): bool(objects.get(oid, False)) for (oid,) in conn.execute('SELECT id FROM objects_settings')}}
            else:
                overrides = {'modules': current[0], 'objects': {str(k): v['selection'] for k, v in current[1].items()}}
        conn.execute('INSERT INTO access_memberships(user_id,department_id,overrides) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET department_id=excluded.department_id,overrides=excluded.overrides', (uid, department_id, json.dumps(overrides)))
