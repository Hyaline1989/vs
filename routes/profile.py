# routes/profile.py
# -*- coding: utf-8 -*-
import os
import uuid
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from database import (
    update_user_profile, change_user_password,
    get_user_avatar, save_user_avatar, delete_user_avatar,
    log_user_action
)

logger = logging.getLogger(__name__)

profile_bp = Blueprint('profile', __name__, url_prefix='/api/profile')

# ========== ОГРАНИЧЕНИЯ ДЛЯ АВАТАРОВ ==========
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB
MIN_AVATAR_SIZE = 1 * 1024  # 1 KB
MAX_TOTAL_AVATARS = 500  # Максимальное количество аватаров в системе
AVATAR_QUALITY = 85
AVATAR_MAX_WIDTH = 500
AVATAR_MAX_HEIGHT = 500

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_upload_dir():
    """Создаёт директорию для загрузки аватаров, если её нет"""
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir

def compress_and_resize_image(file_path, max_width=AVATAR_MAX_WIDTH, max_height=AVATAR_MAX_HEIGHT, quality=AVATAR_QUALITY):
    """Сжимает и изменяет размер изображения"""
    try:
        from PIL import Image
        
        with Image.open(file_path) as img:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            # Изменяем размер с сохранением пропорций
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Сохраняем с оптимизацией
            img.save(file_path, 'JPEG', quality=quality, optimize=True)
            
        return True
    except ImportError:
        logger.warning("PIL не установлен, сжатие изображений недоступно")
        return False
    except Exception as e:
        logger.error(f"Ошибка при сжатии изображения: {e}")
        return False

def cleanup_old_avatars():
    """Удаляет старые неиспользуемые аватары"""
    try:
        upload_dir = ensure_upload_dir()
        all_files = os.listdir(upload_dir)
        
        import sqlite3
        from database import DB_NAME
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT avatar_filename FROM user_avatars')
        used_avatars = set(row[0] for row in cursor.fetchall())
        conn.close()
        
        deleted_count = 0
        for filename in all_files:
            if filename not in used_avatars:
                file_path = os.path.join(upload_dir, filename)
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Ошибка удаления файла {filename}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Очищено {deleted_count} неиспользуемых аватаров")
        
        return deleted_count
    except Exception as e:
        logger.error(f"Ошибка очистки аватаров: {e}")
        return 0

def get_total_avatars_count():
    """Возвращает общее количество аватаров в системе"""
    try:
        upload_dir = ensure_upload_dir()
        return len([f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))])
    except Exception:
        return 0

@profile_bp.route('', methods=['GET'])
@login_required
def get_profile():
    """Получение профиля текущего пользователя"""
    avatar = get_user_avatar(current_user.id)
    avatar_url = f'/static/uploads/avatars/{avatar}' if avatar else None
    
    return jsonify({
        'id': current_user.id,
        'username': current_user.username,
        'full_name': current_user.full_name or '',
        'email': current_user.email or '',
        'role': current_user.role,
        'role_display': current_user.get_role_display_name(),
        'avatar_url': avatar_url,
        'created_at': current_user.created_at,
        'last_login': current_user.last_login
    })

@profile_bp.route('', methods=['PUT'])
@login_required
def update_profile():
    """Обновление профиля (ФИО, email)"""
    data = request.get_json()
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    
    if email and '@' not in email:
        return jsonify({'error': 'Некорректный email'}), 400
    
    success = update_user_profile(current_user.id, full_name or None, email or None)
    
    if success:
        current_user.full_name = full_name
        current_user.email = email
        
        log_user_action(current_user.id, 'update_profile', f"Обновлён профиль", request.remote_addr)
        return jsonify({'success': True, 'message': 'Профиль обновлён'})
    else:
        return jsonify({'error': 'Ошибка при обновлении профиля'}), 500

@profile_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Изменение пароля"""
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    
    if not current_user.check_password(old_password):
        return jsonify({'error': 'Неверный текущий пароль'}), 400
    
    if len(new_password) < 4:
        return jsonify({'error': 'Новый пароль должен быть не менее 4 символов'}), 400
    
    if new_password != confirm_password:
        return jsonify({'error': 'Пароли не совпадают'}), 400
    
    new_password_hash = generate_password_hash(new_password)
    success = change_user_password(current_user.id, new_password_hash)
    
    if success:
        log_user_action(current_user.id, 'change_password', f"Изменён пароль", request.remote_addr)
        return jsonify({'success': True, 'message': 'Пароль успешно изменён'})
    else:
        return jsonify({'error': 'Ошибка при изменении пароля'}), 500

@profile_bp.route('/avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Загрузка аватара с ограничениями"""
    if 'avatar' not in request.files:
        return jsonify({'error': 'Файл не выбран'}), 400
    
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'Неподдерживаемый формат. Разрешены: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_AVATAR_SIZE:
        return jsonify({'error': f'Файл слишком большой. Максимум {MAX_AVATAR_SIZE // (1024*1024)} MB'}), 400
    
    if size < MIN_AVATAR_SIZE:
        return jsonify({'error': f'Файл слишком маленький. Минимум 1 KB'}), 400
    
    total_avatars = get_total_avatars_count()
    if total_avatars >= MAX_TOTAL_AVATARS:
        cleanup_old_avatars()
        total_avatars = get_total_avatars_count()
        if total_avatars >= MAX_TOTAL_AVATARS:
            return jsonify({'error': f'Достигнут лимит аватаров в системе ({MAX_TOTAL_AVATARS}). Обратитесь к администратору'}), 400
    
    old_avatar = get_user_avatar(current_user.id)
    if old_avatar:
        upload_dir = ensure_upload_dir()
        old_path = os.path.join(upload_dir, old_avatar)
        if os.path.exists(old_path):
            os.remove(old_path)
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    new_filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.jpg"
    
    upload_dir = ensure_upload_dir()
    file_path = os.path.join(upload_dir, new_filename)
    file.save(file_path)
    
    compress_and_resize_image(file_path)
    
    save_user_avatar(current_user.id, new_filename)
    
    log_user_action(current_user.id, 'upload_avatar', f"Загружен новый аватар", request.remote_addr)
    
    return jsonify({
        'success': True,
        'avatar_url': f'/static/uploads/avatars/{new_filename}',
        'message': 'Аватар загружен'
    })

@profile_bp.route('/avatar', methods=['DELETE'])
@login_required
def remove_avatar():
    """Удаление аватара"""
    old_avatar = get_user_avatar(current_user.id)
    if old_avatar:
        upload_dir = ensure_upload_dir()
        old_path = os.path.join(upload_dir, old_avatar)
        if os.path.exists(old_path):
            os.remove(old_path)
    
    delete_user_avatar(current_user.id)
    
    log_user_action(current_user.id, 'delete_avatar', f"Удалён аватар", request.remote_addr)
    
    return jsonify({'success': True, 'message': 'Аватар удалён'})

@profile_bp.route('/cleanup', methods=['POST'])
@login_required
def cleanup_avatars():
    """Очистка неиспользуемых аватаров (только для админа)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Доступ только для администратора'}), 403
    
    deleted = cleanup_old_avatars()
    return jsonify({'success': True, 'deleted': deleted, 'message': f'Удалено {deleted} неиспользуемых аватаров'})