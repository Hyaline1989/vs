import sqlite3
from urllib.parse import urlsplit
from flask import Blueprint, request, jsonify
from flask_login import current_user
from database.db_core import DB_NAME
import candidate_rates as store

candidate_rates_bp = Blueprint('candidate_rates', __name__, url_prefix='/api/reports/candidate-rates')


@candidate_rates_bp.before_request
def access():
    if not current_user.is_authenticated:
        return jsonify(error='Требуется вход'), 401
    if not current_user.can_view_reports():
        return jsonify(error='Нет доступа к отчётам'), 403
    if request.method == 'POST':
        origin = request.headers.get('Origin')
        if not request.is_json or (origin and urlsplit(origin).netloc != request.host):
            return jsonify(error='Недопустимый запрос'), 403


@candidate_rates_bp.errorhandler(ValueError)
def invalid(error):
    return jsonify(error=str(error)), 409 if isinstance(error, store.RatesConflict) else 400


@candidate_rates_bp.errorhandler(sqlite3.Error)
def database_error(error):
    from flask import current_app
    current_app.logger.exception('Ошибка базы ставок')
    return jsonify(error='Не удалось прочитать или сохранить ставки. Проверьте подготовку базы ставок.'), 503


@candidate_rates_bp.get('')
def calendar():
    return jsonify(store.read_calendar(DB_NAME, request.args.get('month')))


def selection():
    try:
        oid = int(request.args.get('object_id', ''))
    except ValueError:
        raise ValueError('Выберите объект')
    return oid, request.args.get('from'), request.args.get('to')


@candidate_rates_bp.get('/preview')
def preview():
    return jsonify(store.read_preview(DB_NAME, *selection()))


@candidate_rates_bp.get('/history')
def history():
    return jsonify(rows=store.read_history(DB_NAME, *selection()))


@candidate_rates_bp.post('')
def save():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError('Ожидаются данные ставки')
    return jsonify(store.save_rates(DB_NAME, data, current_user.id, current_user.full_name or current_user.username))
