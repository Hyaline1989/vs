"""Department administration; only administrators may change shared policies."""
import json
import hashlib
import sqlite3
from contextlib import closing
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request
from flask_login import current_user
from database.db_core import DB_NAME
from access_policy import MODULES, ready, validate_policy, assign, effective

departments_bp = Blueprint('departments', __name__, url_prefix='/api/departments')


@departments_bp.before_request
def authorize():
    if not current_user.is_authenticated:
        return jsonify(error='Войдите в систему'), 401
    if current_user.role != 'admin':
        return jsonify(error='Управлять отделами может только администратор'), 403
    if request.method in ('POST', 'PUT'):
        origin = request.headers.get('Origin')
        if origin and urlsplit(origin).netloc != request.host:
            return jsonify(error='Запрос с другого сайта запрещён'), 403
    with closing(sqlite3.connect(DB_NAME)) as conn:
        if not ready(conn):
            return jsonify(error='Отделы ещё не активированы: требуется отдельное обновление базы'), 409


@departments_bp.errorhandler(ValueError)
def invalid(error):
    return jsonify(error=str(error)), 400


@departments_bp.errorhandler(sqlite3.IntegrityError)
def conflict(error):
    return jsonify(error='Отдел с таким названием уже существует или данные конфликтуют'), 409


@departments_bp.route('', methods=['GET'])
def list_departments():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        departments = [dict(id=r[0], name=r[1], **json.loads(r[2])) for r in conn.execute('SELECT id,name,policy FROM access_departments ORDER BY name')]
        users = [dict(id=r[0], name=r[1] or r[2], department_id=r[3], legacy=r[4] is None) for r in conn.execute("SELECT u.id,u.full_name,u.username,m.department_id,m.user_id FROM users u LEFT JOIN access_memberships m ON m.user_id=u.id WHERE u.role!='admin' ORDER BY u.full_name,u.username")]
        objects = [dict(id=r[0], name=r[1]) for r in conn.execute('SELECT id,name FROM objects_settings ORDER BY name')]
    return jsonify(departments=departments, users=users, objects=objects)


@departments_bp.route('', methods=['POST'])
@departments_bp.route('/<int:department_id>', methods=['PUT'])
def save_department(department_id=None):
    data = request.get_json()
    if not isinstance(data, dict):
        raise ValueError('Неверные данные')
    name = data.get('name', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError('Название отдела должно содержать от 1 до 100 символов')
    policy = validate_policy(data)
    with closing(sqlite3.connect(DB_NAME)) as conn, conn:
        if department_id is None:
            department_id = conn.execute('INSERT INTO access_departments(name,policy) VALUES(?,?)', (name.strip(), json.dumps(policy))).lastrowid
        elif conn.execute('UPDATE access_departments SET name=?,policy=? WHERE id=?', (name.strip(), json.dumps(policy), department_id)).rowcount != 1:
            raise ValueError('Отдел не найден')
    return jsonify(success=True, id=department_id)


@departments_bp.route('/assign', methods=['POST'])
def assign_users():
    data = request.get_json()
    if not isinstance(data, dict):
        raise ValueError('Неверные данные')
    did = data.get('department_id')
    if did is not None and type(did) is not int:
        raise ValueError('Неверный отдел')
    with closing(sqlite3.connect(DB_NAME)) as conn, conn:
        ids = data.get('user_ids')
        if not isinstance(ids, list) or not ids or any(type(uid) is not int for uid in ids):
            raise ValueError('Выберите сотрудников')
        previous = dict(conn.execute(f"SELECT user_id,department_id FROM access_memberships WHERE user_id IN ({','.join('?' for _ in ids)})", ids))
        inheriting = [uid for uid in ids if did is not None and previous.get(uid) is None]
        preserving = [uid for uid in ids if uid not in inheriting]
        before = {uid: _permissions_snapshot(conn, uid) for uid in preserving}
        if inheriting:
            assign(conn, inheriting, did, 'inherit')
        if preserving:
            assign(conn, preserving, did, 'preserve')
        if any(_permissions_snapshot(conn, uid) != before[uid] for uid in preserving):
            raise ValueError('Назначение отменено: обнаружено изменение действующих прав')
    return jsonify(success=True)


def _permissions_snapshot(conn, uid):
    role = conn.execute('SELECT role FROM users WHERE id=?', (uid,)).fetchone()
    if not role or role[0] == 'admin':
        raise ValueError('Выберите сотрудника не из администраторов')
    current = effective(conn, uid)
    if current is None:
        legacy = dict(conn.execute('SELECT module_name,can_view FROM user_module_permissions WHERE user_id=?', (uid,)))
        modules = {name: bool(legacy.get(name, False)) for name in MODULES}
        modules['admin'] = role[0] == 'manager'
        objects = {oid: (bool(dashboard), bool(selection)) for oid, dashboard, selection in conn.execute('SELECT object_id,can_view_dashboard,can_view_selection FROM user_object_permissions WHERE user_id=?', (uid,))}
    else:
        modules, object_access = current
        objects = {oid: (flags['dashboard'], flags['selection']) for oid, flags in object_access.items()}
    object_ids = [oid for (oid,) in conn.execute('SELECT id FROM objects_settings')]
    return {'modules': modules,
            'objects': {str(oid): objects.get(oid, (False, False))[1] for oid in object_ids},
            'dashboard_objects': {str(oid): objects.get(oid, (False, False))[0] for oid in object_ids}}


def _assignment_preview(conn, user_id, department_id):
    department = conn.execute('SELECT policy FROM access_departments WHERE id=?', (department_id,)).fetchone()
    if not department:
        raise ValueError('Отдел не найден')
    policy = json.loads(department[0])
    before = _permissions_snapshot(conn, user_id)
    object_ids = [oid for (oid,) in conn.execute('SELECT id FROM objects_settings')]
    after = {'modules': {name: bool(policy.get('modules', {}).get(name, False)) for name in MODULES},
             'objects': {str(oid): bool(policy.get('objects', {}).get(str(oid), policy.get('all_objects', False))) for oid in object_ids},
             'dashboard_objects': {str(oid): True for oid in object_ids}}
    changes = {'modules': {name: {'before': before['modules'][name], 'after': after['modules'][name]}
                           for name in MODULES if before['modules'][name] != after['modules'][name]},
               'objects_granted': sum(not before['objects'][str(oid)] and after['objects'][str(oid)] for oid in object_ids),
               'objects_revoked': sum(before['objects'][str(oid)] and not after['objects'][str(oid)] for oid in object_ids),
               'dashboard_objects_changed': sum(before['dashboard_objects'][str(oid)] != after['dashboard_objects'][str(oid)] for oid in object_ids)}
    token = hashlib.sha256(json.dumps({'before': before, 'after': after, 'department_id': department_id}, sort_keys=True).encode()).hexdigest()
    return changes, token


@departments_bp.route('/assignment-preview', methods=['POST'])
def assignment_preview():
    data = request.get_json(silent=True) or {}
    uid, did = data.get('user_id'), data.get('department_id')
    if type(did) is not int:
        raise ValueError('Выберите сотрудника и отдел')
    if type(uid) is not int:
        raise ValueError('Выберите сотрудника и отдел')
    with closing(sqlite3.connect(DB_NAME)) as conn:
        changes, token = _assignment_preview(conn, uid, did)
    return jsonify(changes=changes, token=token)


@departments_bp.route('/apply-department', methods=['POST'])
def apply_department():
    data = request.get_json(silent=True) or {}
    uid, did = data.get('user_id'), data.get('department_id')
    if type(did) is not int or not isinstance(data.get('token'), str):
        raise ValueError('Сначала просмотрите изменения прав')
    if type(uid) is not int:
        raise ValueError('Сначала просмотрите изменения прав')
    with closing(sqlite3.connect(DB_NAME)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        _, token = _assignment_preview(conn, uid, did)
        if data['token'] != token:
            raise ValueError('Права изменились после просмотра. Просмотрите изменения заново.')
        assign(conn, [uid], did, 'inherit')
    return jsonify(success=True)


@departments_bp.route('/users/<int:user_id>', methods=['GET', 'PUT'])
def user_policy(user_id):
    with closing(sqlite3.connect(DB_NAME)) as conn, conn:
        user = conn.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
        if not user or user[0] == 'admin':
            raise ValueError('Выберите сотрудника. Администраторы сохраняют полный доступ.')
        if request.method == 'PUT':
            policy = validate_policy(request.get_json(), override=True)
            current = effective(conn, user_id)
            if current is None:
                if set(policy['modules']) != set(MODULES) or set(policy['objects']) != {str(oid) for (oid,) in conn.execute('SELECT id FROM objects_settings')}:
                    raise ValueError('Укажите права всех разделов и объектов')
                old_dashboard = {str(oid): bool(value) for oid, value in conn.execute('SELECT object_id,can_view_dashboard FROM user_object_permissions WHERE user_id=?', (user_id,))}
                for module in MODULES:
                    if module == 'admin':
                        if policy['modules'][module] != (user[0] == 'manager'):
                            raise ValueError('Доступ к админ-панели без отдела определяется ролью')
                        continue
                    conn.execute('INSERT INTO user_module_permissions(user_id,module_name,can_view) VALUES(?,?,?) ON CONFLICT(user_id,module_name) DO UPDATE SET can_view=excluded.can_view',
                                 (user_id, module, int(policy['modules'][module])))
                for key, allowed in policy['objects'].items():
                    conn.execute('INSERT INTO user_object_permissions(user_id,object_id,can_view_dashboard,can_view_selection) VALUES(?,?,?,?) ON CONFLICT(user_id,object_id) DO UPDATE SET can_view_selection=excluded.can_view_selection',
                                 (user_id, int(key), int(old_dashboard.get(key, False)), int(allowed)))
            else:
                previous = conn.execute('SELECT overrides FROM access_memberships WHERE user_id=?', (user_id,)).fetchone()
                if previous is None:
                    raise ValueError('Не удалось сохранить исключения')
                if 'dashboard_objects' not in (request.get_json(silent=True) or {}):
                    policy['dashboard_objects'] = json.loads(previous[0]).get('dashboard_objects', {})
                conn.execute('UPDATE access_memberships SET overrides=? WHERE user_id=?', (json.dumps(policy), user_id))
        row = conn.execute('SELECT department_id,overrides FROM access_memberships WHERE user_id=?', (user_id,)).fetchone()
        if row:
            return jsonify(department_id=row[0], overrides=json.loads(row[1]), effective=effective(conn, user_id), legacy=False)
        modules = dict(conn.execute('SELECT module_name,can_view FROM user_module_permissions WHERE user_id=?', (user_id,)))
        modules = {name: bool(modules.get(name, False)) for name in MODULES}
        modules['admin'] = user[0] == 'manager'
        object_rows = {oid: (bool(dashboard), bool(selection)) for oid, dashboard, selection in conn.execute('SELECT object_id,can_view_dashboard,can_view_selection FROM user_object_permissions WHERE user_id=?', (user_id,))}
        objects = {oid: {'dashboard': object_rows.get(oid, (False, False))[0], 'selection': object_rows.get(oid, (False, False))[1]}
                   for (oid,) in conn.execute('SELECT id FROM objects_settings')}
        return jsonify(department_id=None, overrides=None, effective=[modules, objects], legacy=True)
