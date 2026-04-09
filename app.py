# app.py - рефакторинг с использованием Blueprint и отдельными страницами
# -*- coding: utf-8 -*-
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_required, current_user
from datetime import datetime, timedelta
import logging
import atexit
import redis
from apscheduler.schedulers.background import BackgroundScheduler

from config import *
from bitrix_api import BitrixAPI
from google_sheets import GoogleSheetsAPI
from comparer import DataComparer
from database import init_db, cleanup_old_records, init_objects_settings, init_vacancy_tables
from models import User

# Импортируем blueprint'ы и их инициализаторы
from routes import (
    auth_bp, admin_bp, dashboard_bp, selection_bp, admin_pages_bp, objects_admin_bp,
    init_dashboard_apis, init_selection_apis
)
from routes.requirements_admin import requirements_admin_bp

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
login_manager.login_view = None
login_manager.session_protection = "strong"

@login_manager.user_loader
def load_user(user_id):
    """Загружает пользователя по ID для Flask-Login"""
    from database import get_user_by_id
    try:
        user_data = get_user_by_id(user_id)
        if user_data:
            return User(user_data)
    except Exception as e:
        logger.error(f"Ошибка загрузки пользователя {user_id}: {e}")
    return None

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
google_api = GoogleSheetsAPI()
comparer = DataComparer(bitrix_api, google_api)

# Инициализируем blueprint'ы с API
init_dashboard_apis(bitrix_api, google_api, comparer)
# Для selection_api больше не передаём google_api (используем БД)
init_selection_apis(None)

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========
if init_db():
    logger.info("✅ База данных успешно инициализирована")
    init_objects_settings()
    # Инициализируем таблицы для вакансий
    if init_vacancy_tables():
        logger.info("✅ Таблицы вакансий успешно инициализированы")
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

# ========== СТРАНИЦЫ ==========
@app.route('/')
def index():
    """Главная страница - страница входа"""
    return render_template('index.html')

@app.route('/welcome')
@login_required
def welcome():
    """Приветственная страница после входа"""
    return render_template('welcome.html')

@app.route('/dashboard')
@login_required
def dashboard_page():
    """Страница дашборда"""
    try:
        # Проверяем права доступа к модулю
        if not current_user.can_view_dashboard():
            logger.warning(f"Пользователь {current_user.username} пытается зайти в дашборд без прав")
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
    """Страница подбора объектов"""
    try:
        # Проверяем права доступа к модулю
        if not current_user.can_view_selection():
            logger.warning(f"Пользователь {current_user.username} пытается зайти в подбор объектов без прав")
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
    """Страница управления пользователями и объектами"""
    try:
        # Проверяем права доступа
        if current_user.role not in ['admin', 'manager']:
            logger.warning(f"Пользователь {current_user.username} пытается зайти в админку без прав")
            return render_template('no_access.html', 
                                 message="У вас нет доступа к админ-панели",
                                 return_url="/welcome"), 403
        
        return render_template('admin_panel.html')
    except Exception as e:
        logger.error(f"Ошибка при загрузке admin_panel: {e}", exc_info=True)
        return render_template('no_access.html', 
                             message="Произошла ошибка при загрузке страницы",
                             return_url="/welcome"), 500

# ========== ДИАГНОСТИЧЕСКИЕ ЭНДПОИНТЫ ==========
@app.route('/api/debug/google-sheets')
def debug_google_sheets():
    """Диагностический эндпоинт для проверки Google Sheets (только для админов)"""
    from flask_login import current_user
    from database import get_all_max_requirements
    from datetime import datetime
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    # Запускаем диагностику
    try:
        google_api.debug_csv_content()
    except Exception as e:
        logger.error(f"Ошибка при диагностике: {e}")
        return jsonify({'error': str(e)}), 500
    
    # Получаем данные из БД за сегодня
    today_data = get_all_max_requirements(datetime.now())
    
    # Получаем данные из БД за последние 7 дней
    from datetime import timedelta
    week_data = {}
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        week_data[date.strftime('%Y-%m-%d')] = len(get_all_max_requirements(date))
    
    return jsonify({
        'status': 'ok',
        'today_requirements_count': len(today_data),
        'today_requirements': {k: v for k, v in list(today_data.items())[:20]},
        'week_requirements_counts': week_data,
        'message': 'Диагностика завершена, смотрите логи сервера'
    })

@app.route('/api/debug/database')
def debug_database():
    """Диагностический эндпоинт для проверки базы данных"""
    from flask_login import current_user
    from database import get_all_max_requirements, get_all_dates, get_all_vacancy_data
    from datetime import datetime, timedelta
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    all_dates = get_all_dates()
    
    # Получаем статистику по последним 7 дням
    stats = {}
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        data = get_all_max_requirements(date)
        stats[date_str] = {
            'count': len(data),
            'total_need': sum(item['count'] for item in data.values()),
            'priority_count': sum(1 for item in data.values() if item.get('is_high', False))
        }
    
    # Получаем статистику по вакансиям из новой системы
    today_vacancy = get_all_vacancy_data(datetime.now().strftime('%Y-%m-%d'))
    vacancy_stats = {
        'total_objects': len(today_vacancy),
        'total_positions': sum(len(v.get('positions', [])) for v in today_vacancy.values()),
        'total_need': sum(
            v.get('rf', {}).get('men', 0) + v.get('rf', {}).get('women', 0) + v.get('rf', {}).get('family', 0) +
            v.get('cis', {}).get('men', 0) + v.get('cis', {}).get('women', 0) + v.get('cis', {}).get('family', 0)
            for v in today_vacancy.values()
        )
    }
    
    return jsonify({
        'status': 'ok',
        'all_dates': all_dates[:30],
        'last_7_days_stats': stats,
        'vacancy_stats': vacancy_stats,
        'database_file': 'requirements.db'
    })

@app.route('/api/debug/priority-check')
def debug_priority_check():
    """Диагностический эндпоинт для проверки приоритетов в БД"""
    from flask_login import current_user
    from database import get_all_max_requirements
    from datetime import datetime
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    today = datetime.now()
    requirements = get_all_max_requirements(today)
    
    priority_objects = []
    for name, data in requirements.items():
        if data.get('is_high', False):
            priority_objects.append({
                'name': name,
                'count': data['count'],
                'is_high': data['is_high']
            })
    
    return jsonify({
        'date': today.strftime('%Y-%m-%d'),
        'total_objects': len(requirements),
        'priority_objects': priority_objects,
        'all_requirements': {k: v for k, v in list(requirements.items())[:20]}
    })

@app.route('/api/debug/csv-structure')
@login_required
def debug_csv_structure():
    """Диагностика структуры CSV (только для админов)"""
    from flask_login import current_user
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        result = google_api.debug_csv_structure()
        return jsonify({'status': 'ok', 'message': 'Смотрите логи сервера для деталей'})
    except Exception as e:
        logger.error(f"Ошибка диагностики CSV: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/vacancy-data')
@login_required
def debug_vacancy_data():
    """Проверка данных вакансий из БД (только для админов)"""
    from flask_login import current_user
    from database import get_all_vacancy_data
    from datetime import datetime
    
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        # Получаем данные из новой БД
        vacancy_data = get_all_vacancy_data(datetime.now().strftime('%Y-%m-%d'))
        
        # Ограничиваем вывод для безопасности
        limited_data = {}
        for obj_name, data in list(vacancy_data.items())[:20]:
            limited_data[obj_name] = {
                'rf_men': data.get('rf', {}).get('men', 0),
                'rf_women': data.get('rf', {}).get('women', 0),
                'rf_family': data.get('rf', {}).get('family', 0),
                'cis_men': data.get('cis', {}).get('men', 0),
                'cis_women': data.get('cis', {}).get('women', 0),
                'cis_family': data.get('cis', {}).get('family', 0),
                'positions_count': len(data.get('positions', [])),
                'positions': [p.get('name', '') for p in data.get('positions', [])[:5]]
            }
        
        return jsonify({
            'source': 'DATABASE (new system)',
            'total_objects': len(vacancy_data),
            'data': limited_data
        })
    except Exception as e:
        logger.error(f"Ошибка получения данных вакансий из БД: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/migrate-status')
@login_required
def debug_migrate_status():
    """Проверка статуса миграции данных"""
    from flask_login import current_user
    from database import get_all_vacancy_data
    from datetime import datetime
    
    if not current_user.is_authenticated or not current_user.is_admin():
        return jsonify({'error': 'Forbidden'}), 403
    
    try:
        # Проверяем наличие данных в новой системе
        today = datetime.now().strftime('%Y-%m-%d')
        vacancy_count = len(get_all_vacancy_data(today))
        
        # Проверяем наличие данных в старой системе (Google Sheets)
        old_vacancy = google_api.get_vacancy_data() if google_api else {}
        old_count = len(old_vacancy)
        
        return jsonify({
            'new_system': {
                'has_data': vacancy_count > 0,
                'objects_count': vacancy_count,
                'date': today
            },
            'old_system': {
                'has_data': old_count > 0,
                'objects_count': old_count
            },
            'needs_migration': vacancy_count == 0 and old_count > 0
        })
    except Exception as e:
        logger.error(f"Ошибка проверки статуса миграции: {e}")
        return jsonify({'error': str(e)}), 500

# ========== ФОНОВЫЕ ЗАДАЧИ ==========
def update_requirements_for_last_n_days(n_days=7):
    today = datetime.now()
    updated_count = 0
    for i in range(n_days):
        target_date = today - timedelta(days=i)
        if google_api.update_requirements_for_date(target_date):
            updated_count += 1
    return updated_count

scheduler = BackgroundScheduler()
# Фоновые задачи для Google Sheets отключены (переходим на ручное управление через БД)
scheduler.add_job(func=cleanup_old_records, trigger="cron", hour=3, minute=0, args=[30], 
                  id='cleanup_database')
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ========== HEALTH CHECK ==========
@app.route('/api/health')
def health():
    from database import get_all_vacancy_data
    today_vacancy = get_all_vacancy_data(datetime.now().strftime('%Y-%m-%d'))
    
    return jsonify({
        'status': 'ok',
        'time': datetime.now().isoformat(),
        'database': 'connected',
        'vacancy_objects': len(today_vacancy)
    })

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == '__main__':
    logger.info("🚀 Запуск объединённого CRM Dashboard...")
    logger.info("📊 Система управления вакансиями переведена на БД (без Google Sheets)")
    debug_mode = FLASK_ENV == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=5001)