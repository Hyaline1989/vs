"""Отчёт по плановому убытию и защищённый приём обезличенной сводки."""

import hmac
import logging
import os

from flask import Blueprint, jsonify, request
from flask_login import current_user

from planned_departures_store import (
    days_in_month, read_snapshot, totals_for, validate_snapshot, write_snapshot,
)
from report_refresh_store import finish_refresh


planned_departures_bp = Blueprint('planned_departures', __name__, url_prefix='/api/reports/planned-departures')
logger = logging.getLogger(__name__)


@planned_departures_bp.get('')
def get_planned_departures():
    if not current_user.is_authenticated:
        return jsonify(error='Unauthorized'), 401
    if not current_user.can_view_reports():
        return jsonify(error='Forbidden'), 403
    month = request.args.get('month', '')
    try:
        days_in_month(month)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    try:
        snapshot = read_snapshot(month)
    except (OSError, ValueError) as error:
        logger.error('Не удалось прочитать отчёт об убытии за %s: %s', month, error)
        return jsonify(error='Не удалось прочитать сохранённый отчёт'), 500
    if snapshot is None:
        return jsonify(status='not_loaded', month=month)
    return jsonify(status='ready', **snapshot, totals=totals_for(snapshot))


@planned_departures_bp.post('/import')
def import_planned_departures():
    expected = os.environ.get('PLANNED_DEPARTURES_IMPORT_KEY', '')
    if len(expected) < 32:
        return jsonify(error='Приём отчёта не настроен'), 503
    provided = request.headers.get('X-Vector-Import-Key', '')
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        return jsonify(error='Unauthorized'), 401
    if request.content_length is not None and request.content_length > 256 * 1024:
        return jsonify(error='Слишком большой отчёт'), 413
    try:
        snapshot = validate_snapshot(request.get_json(silent=True))
        write_snapshot(snapshot)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError as error:
        logger.error('Не удалось сохранить отчёт об убытии: %s', error)
        return jsonify(error='Не удалось сохранить отчёт'), 500
    refresh_id = request.headers.get('X-Vector-Refresh-Id', '')
    if refresh_id:
        try:
            finish_refresh('departures', snapshot['month'], refresh_id, 'completed')
        except OSError as error:
            logger.error('Не удалось отметить обновление отчёта об убытии: %s', error)
    return jsonify(status='saved', month=snapshot['month'], objects=len(snapshot['objects']))
