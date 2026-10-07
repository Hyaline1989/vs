"""Department administration; only administrators may change shared policies."""
import json
import sqlite3
from contextlib import closing
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request
from flask_login import current_user
from database.db_core import DB_NAME
from access_policy import ready, validate_policy, assign, effective

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
        users = [dict(id=r[0], name=r[1] or r[2], department_id=r[3]) for r in conn.execute("SELECT u.id,u.full_name,u.username,m.department_id FROM users u LEFT JOIN access_memberships m ON m.user_id=u.id WHERE u.role!='admin' ORDER BY u.full_name,u.username")]
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
        # A transfer always replaces old permissions, even from a cached old UI.
        assign(conn, data.get('user_ids'), did, 'inherit' if did is not None else 'preserve')
    return jsonify(success=True)


@departments_bp.route('/users/<int:user_id>', methods=['GET', 'PUT'])
def user_policy(user_id):
    with closing(sqlite3.connect(DB_NAME)) as conn, conn:
        user = conn.execute('SELECT role FROM users WHERE id=?', (user_id,)).fetchone()
        if not user or user[0] == 'admin':
            raise ValueError('Выберите сотрудника. Администраторы сохраняют полный доступ.')
        if request.method == 'PUT':
            policy = validate_policy(request.get_json(), override=True)
            if conn.execute('UPDATE access_memberships SET overrides=? WHERE user_id=?', (json.dumps(policy), user_id)).rowcount != 1:
                raise ValueError('Сначала назначьте сотруднику отдел')
        row = conn.execute('SELECT department_id,overrides FROM access_memberships WHERE user_id=?', (user_id,)).fetchone()
        return jsonify(department_id=row[0] if row else None, overrides=json.loads(row[1]) if row else None, effective=effective(conn, user_id))
