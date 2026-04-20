# app.py - рефакторинг с использованием Blueprint и отдельными страницами
# -*- coding: utf-8 -*-
from flask import Flask, render_template, jsonify, request, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_required, current_user
from datetime import datetime, timedelta, timezone
import logging
import atexit
import redis
from apscheduler.schedulers.background import BackgroundScheduler

# Московское время UTC+3
MOSCOW_OFFSET = timedelta(hours=3)

def get_moscow_now():
    return datetime.now(timezone.utc) + MOSCOW_OFFSET

def get_moscow_date():
    return (datetime.now(timezone.utc) + MOSCOW_OFFSET).strftime('%Y-%m-%d')

from config import *
from bitrix_api import BitrixAPI
from comparer import DataComparer
from database import init_db, cleanup_old_records, init_objects_settings, init_vacancy_tables, cleanup_old_unused_avatars, init_current_requirements_table
from models import User

# Импортируем blueprint'ы
from routes import (
    auth_bp, admin_bp, dashboard_bp, selection_bp, admin_pages_bp, objects_admin_bp,
    init_dashboard_apis
)
from routes.requirements_admin import requirements_admin_bp
from routes.profile import profile_bp

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== СОЗДАНИЕ FLASK ПРИЛОЖЕНИЯ ==========
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(hours=SESSION_DURATION_HOURS)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=SESSION_DURATION_HOURS)

# Настройка CORS
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

# ========== НАСТРОЙКА FLASK-LOGIN ==========
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'
login_manager.login_message = False
login_manager.session_protection = "strong"

@login_manager.user_loader
def load_user(user_id):
    from database import get_user_by_id
    try:
        user_data = get_user_by_id(user_id)
        if user_data:
            return User(user_data)
    except Exception as e:
        logger.error(f"Ошибка загрузки пользователя {user_id}: {e}")
    return None

@login_manager.unauthorized_handler
def unauthorized():
    return redirect('/')

# ========== НАСТРОЙКА REDIS ДЛЯ RATE LIMITING ==========
redis_available = False
try:
    if REDIS_URL:
        redis_client = redis.from_url(REDIS_URL, socket_timeout=REDIS_SOCKET_TIMEOUT, decode_responses=True)
        redis_client.ping()
        redis_available = True
        logger.info(f"✅ Redis подключен успешно")
except Exception as e:
    logger.warning(f"⚠️ Redis недоступен ({e})")

if redis_available:
    limiter = Limiter(app=app, key_func=get_remote_address, storage_uri=REDIS_URL, default_limits=[RATE_LIMIT_DEFAULT])
else:
    limiter = Limiter(app=app, key_func=get_remote_address, default_limits=[RATE_LIMIT_DEFAULT])

# ========== ЗАЩИТА ОТ БОЛЬШИХ ЗАПРОСОВ ==========
@app.before_request
def before_request():
    if request.content_length and request.content_length > MAX_CONTENT_LENGTH:
        return jsonify({'error': 'Request too large'}), 413

# ========== КОНТЕКСТНЫЕ ПРОЦЕССОРЫ ДЛЯ ШАБЛОНОВ ==========
@app.context_processor
def inject_globals():
    from flask_login import current_user
    return {
        'current_user': current_user,
        'request': request
    }

# ========== ИНИЦИАЛИЗАЦИЯ API ==========
bitrix_api = BitrixAPI(BITRIX_WEBHOOK_URL)
comparer = DataComparer(bitrix_api)

init_dashboard_apis(bitrix_api, comparer)

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========
if init_db():
    logger.info("✅ База данных успешно инициализирована")
    init_objects_settings()
    if init_vacancy_tables():
        logger.info("✅ Таблицы вакансий успешно инициализированы")
    init_current_requirements_table()
    logger.info("✅ Таблица текущих потребностей инициализирована")
else:
    logger.error("❌ Ошибка при инициализации базы данных")

# ========== РЕГИСТРАЦИЯ BLUEPRINT'ОВ ==========
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(selection_bp)
app.register_blueprint(admin_pages_bp)
app.register_blueprint(objects_admin_bp)
app.register_blueprint(requirements_admin_bp)
app.register_blueprint(profile_bp)

# ========== СТРАНИЦЫ ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/welcome')
@login_required
def welcome():
    return render_template('welcome.html')

@app.route('/dashboard')
@login_required
def dashboard_page():
    try:
        if not current_user.can_view_dashboard():
            return render_template('no_access.html', 
                                 message="У вас нет доступа к дашборду",
                                 return_url="/welcome"), 403
        return render_template('dashboard.html')
    except Exception as e:
        logger.error(f"Ошибка при загрузке dashboard_page: {e}", exc_info=True)
        return render_template('no_access.html', 
                             message="Произошла ошибка при загрузке страницы",
                             return_url="/welcome"), 500

@app.route('/selection')
@login_required
def selection_page():
    try:
        if not current_user.can_view_selection():
            return render_template('no_access.html', 
                                 message="У вас нет доступа к подбору объектов",
                                 return_url="/welcome"), 403
        return render_template('selection.html')
    except Exception as e:
        logger.error(f"Ошибка при загрузке selection_page: {e}", exc_info=True)
        return render_template('no_access.html', 
                             message="Произошла ошибка при загрузке страницы",
                             return_url="/welcome"), 500

@app.route('/admin')
@login_required
def admin_panel():
    try:
        if current_user.role not in ['admin', 'manager']:
            return render_template('no_access.html', 
                                 message="У вас нет доступа к админ-панели",
                                 return_url="/welcome"), 403
        return render_template('admin_panel.html')
    except Exception as e:
        logger.error(f"Ошибка при загрузке admin_panel: {e}", exc_info=True)
        return render_template('no_access.html', 
                             message="Произошла ошибка при загрузке страницы",
                             return_url="/welcome"), 500

@app.route('/profile')
@login_required
def profile_page():
    return render_template('profile.html')

# ========== ФОНОВЫЕ ЗАДАЧИ ==========
scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_old_records, trigger="cron", hour=3, minute=0, args=[30], 
                  id='cleanup_database')
scheduler.add_job(func=cleanup_old_unused_avatars, trigger="cron", hour=3, minute=30, 
                  id='cleanup_avatars')
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ========== HEALTH CHECK ==========
@app.route('/api/health')
def health():
    from database import get_all_vacancy_data
    today_vacancy = get_all_vacancy_data(get_moscow_date())
    
    return jsonify({
        'status': 'ok',
        'time': get_moscow_now().isoformat(),
        'database': 'connected',
        'vacancy_objects': len(today_vacancy)
    })

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == '__main__':
    logger.info("🚀 Запуск объединённого CRM Dashboard...")
    logger.info(f"🕐 Московское время: {get_moscow_now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("📊 Дашборд использует план из БД (вакансии)")
    logger.info("🎯 Подбор объектов использует текущие потребности (без привязки к дате)")
    debug_mode = FLASK_ENV == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=5001)