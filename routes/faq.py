# -*- coding: utf-8 -*-
"""API редактируемого руководства пользователя."""

import os
import uuid

from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user, login_required
from database import (
    create_faq_article,
    delete_faq_article,
    ensure_default_faq,
    get_faq_articles,
    log_user_action,
    update_faq_article,
)


faq_bp = Blueprint('faq_api', __name__, url_prefix='/api')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'jfif', 'webp'}
IMAGE_MIME_EXTENSIONS = {
    'image/png': 'png',
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/pjpeg': 'jpg',
    'image/webp': 'webp',
}
MAX_FAQ_IMAGE_SIZE = 5 * 1024 * 1024


def _admin_required():
    return current_user.role == 'admin'


def _validate_article(data):
    required = ('category_slug', 'category_title', 'title')
    if not isinstance(data, dict) or any(not str(data.get(field, '')).strip() for field in required):
        return 'Заполните категорию и название статьи'
    if not isinstance(data.get('blocks', []), list):
        return 'Некорректное содержимое статьи'
    allowed_types = {'text', 'list', 'steps', 'note', 'image'}
    for block in data.get('blocks', []):
        if not isinstance(block, dict) or block.get('type') not in allowed_types:
            return 'В статье найден неизвестный тип блока'
    return None


@faq_bp.route('/faq', methods=['GET'])
@login_required
def public_faq():
    ensure_default_faq()
    return jsonify({'articles': get_faq_articles(False)})


@faq_bp.route('/admin/faq', methods=['GET'])
@login_required
def admin_faq():
    if not _admin_required():
        return jsonify({'error': 'Доступ запрещён'}), 403
    ensure_default_faq()
    return jsonify({'articles': get_faq_articles(True)})


@faq_bp.route('/admin/faq', methods=['POST'])
@login_required
def add_faq_article():
    if not _admin_required():
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = request.get_json(silent=True) or {}
    error = _validate_article(data)
    if error:
        return jsonify({'error': error}), 400
    article_id = create_faq_article(data, current_user.id)
    log_user_action(current_user.id, 'create_faq_article', f'Создана статья FAQ ID {article_id}', request.remote_addr)
    return jsonify({'success': True, 'id': article_id}), 201


@faq_bp.route('/admin/faq/<int:article_id>', methods=['PUT'])
@login_required
def edit_faq_article(article_id):
    if not _admin_required():
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = request.get_json(silent=True) or {}
    error = _validate_article(data)
    if error:
        return jsonify({'error': error}), 400
    if not update_faq_article(article_id, data, current_user.id):
        return jsonify({'error': 'Статья не найдена'}), 404
    log_user_action(current_user.id, 'update_faq_article', f'Обновлена статья FAQ ID {article_id}', request.remote_addr)
    return jsonify({'success': True})


@faq_bp.route('/admin/faq/<int:article_id>', methods=['DELETE'])
@login_required
def remove_faq_article(article_id):
    if not _admin_required():
        return jsonify({'error': 'Доступ запрещён'}), 403
    if not delete_faq_article(article_id):
        return jsonify({'error': 'Статья не найдена'}), 404
    log_user_action(current_user.id, 'delete_faq_article', f'Удалена статья FAQ ID {article_id}', request.remote_addr)
    return jsonify({'success': True})


@faq_bp.route('/admin/faq/images', methods=['POST'])
@login_required
def upload_faq_image():
    if not _admin_required():
        return jsonify({'error': 'Доступ запрещён'}), 403
    image = request.files.get('image')
    if not image or not image.filename:
        return jsonify({'error': 'Выберите изображение'}), 400
    # Расширение читаем из исходного имени. secure_filename может удалить
    # кириллическую часть имени и на некоторых JPG оставить пустой результат.
    extension = os.path.splitext(image.filename)[1].lower().lstrip('.')
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        extension = IMAGE_MIME_EXTENSIONS.get((image.mimetype or '').lower(), '')
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({'error': 'Разрешены PNG, JPG и WEBP'}), 400
    if extension in {'jpeg', 'jfif'}:
        extension = 'jpg'

    image.seek(0, os.SEEK_END)
    size = image.tell()
    image.seek(0)
    if size > MAX_FAQ_IMAGE_SIZE:
        return jsonify({'error': 'Размер изображения не должен превышать 5 МБ'}), 400

    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'faq')
    os.makedirs(upload_dir, exist_ok=True)
    filename = f'{uuid.uuid4().hex}.{extension}'
    image.save(os.path.join(upload_dir, filename))
    image_url = url_for('static', filename=f'uploads/faq/{filename}')
    log_user_action(current_user.id, 'upload_faq_image', f'Загружено изображение FAQ {filename}', request.remote_addr)
    return jsonify({'success': True, 'url': image_url})
