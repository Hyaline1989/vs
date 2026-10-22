"""Запрос и отслеживание пересчёта закрытых Google-табелей."""

import hmac
import logging
import os

from flask import Blueprint, jsonify, request
from flask_login import current_user

from report_refresh_store import claim_pending, finish_refresh, get_refresh, request_refresh


report_refresh_bp = Blueprint('report_refresh', __name__, url_prefix='/api/report-refresh')
logger = logging.getLogger(__name__)


def _user_can_refresh(report):
    if not current_user.is_authenticated:
        return False
    if report == 'departures':
        return current_user.can_view_reports()
    if report == 'shifts':
        return current_user.can_view_vip()
    return False


def _script_key_is_valid():
    expected = os.environ.get('PLANNED_DEPARTURES_IMPORT_KEY', '')
    provided = request.headers.get('X-Vector-Import-Key', '')
    return len(expected) >= 32 and hmac.compare_digest(provided.encode(), expected.encode())


@report_refresh_bp.post('/request')
def request_report_refresh():
    if not current_user.is_authenticated:
        return jsonify(error='Unauthorized'), 401
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(error='Некорректный запрос'), 400
    report = payload.get('report')
    if not _user_can_refresh(report):
        return jsonify(error='Forbidden'), 403
    try:
        saved = request_refresh(report, payload.get('month'))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError as error:
        logger.error('Не удалось поставить пересчёт в очередь: %s', error)
        return jsonify(error='Не удалось запросить обновление'), 500
    return jsonify(id=saved['id'], status=saved['status'], month=saved['month'])


@report_refresh_bp.get('/status')
def report_refresh_status():
    if not current_user.is_authenticated:
        return jsonify(error='Unauthorized'), 401
    report = request.args.get('report')
    if not _user_can_refresh(report):
        return jsonify(error='Forbidden'), 403
    try:
        saved = get_refresh(report, request.args.get('month'), request.args.get('id'))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except (OSError, KeyError) as error:
        logger.error('Не удалось прочитать статус пересчёта: %s', error)
        return jsonify(error='Не удалось проверить обновление'), 500
    if saved is None:
        return jsonify(error='Запрос не найден'), 404
    return jsonify(id=saved['id'], status=saved['status'], month=saved['month'],
                   updated_at=saved['updated_at'])


@report_refresh_bp.get('/pending')
def pending_report_refresh():
    if not _script_key_is_valid():
        return jsonify(error='Unauthorized'), 401
    try:
        pending = claim_pending()
    except (OSError, ValueError, KeyError) as error:
        logger.error('Не удалось выдать запрос на пересчёт: %s', error)
        return jsonify(error='Не удалось получить запрос'), 500
    return jsonify(request=pending)


@report_refresh_bp.post('/failed')
def failed_report_refresh():
    if not _script_key_is_valid():
        return jsonify(error='Unauthorized'), 401
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(error='Некорректный запрос'), 400
    try:
        updated = finish_refresh(payload.get('report'), payload.get('month'),
                                 payload.get('id'), 'error')
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError as error:
        logger.error('Не удалось отметить ошибку пересчёта: %s', error)
        return jsonify(error='Не удалось сохранить статус'), 500
    return jsonify(status='saved' if updated else 'outdated')
