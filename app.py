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
from bitrix_api import BitrixAPI, ShiftReportAPI
from comparer import DataComparer
from database import init_db, cleanup_old_records, init_objects_settings, init_vacancy_tables, cleanup_old_unused_avatars, init_current_requirements_table, init_passports_table, init_daily_snapshots_table, ensure_default_faq
from models import User

# Импортируем blueprint'ы
from routes import (
    auth_bp, admin_bp, dashboard_bp, selection_bp, admin_pages_bp, objects_admin_bp,
    init_dashboard_apis, worker_status_bp, faq_bp, planned_departures_bp,
    service_reports_bp, report_refresh_bp
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
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30 MB для загрузки PDF

# Выводим для отладки
print(f"✅ MAX_CONTENT_LENGTH = {app.config['MAX_CONTENT_LENGTH']} bytes ({app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024} MB)")

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
    # Пропускаем статические файлы
    if request.path.startswith('/static/'):
        return None
    
    # Проверяем только POST и PUT запросы с телом
    if request.method in ['POST', 'PUT'] and request.content_length:
        max_size = app.config.get('MAX_CONTENT_LENGTH', 30 * 1024 * 1024)
        print(f"📦 Запрос {request.method} {request.path}: Content-Length = {request.content_length} bytes, лимит = {max_size} bytes")
        if request.content_length > max_size:
            print(f"❌ Слишком большой запрос!")
            return jsonify({'error': f'Request too large. Max size: {max_size / 1024 / 1024} MB'}), 413
    return None

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
    init_passports_table()
    logger.info("✅ Таблица паспортов объектов инициализирована")
    init_daily_snapshots_table()
    logger.info("✅ Таблица ежедневных снапшотов инициализирована")
    ensure_default_faq()
    logger.info("✅ Руководство FAQ инициализировано")
else:
    logger.error("❌ Ошибка при инициализации базы данных")

# ========== РЕГИСТРАЦИЯ BLUEPRINT'ОВ ==========
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
from routes.departments import departments_bp
app.register_blueprint(departments_bp)


@app.before_request
def department_admin_gate():
    from flask_login import current_user
    protected = (request.path == '/admin' or request.blueprint == 'admin'
                 or (request.method not in ('GET', 'HEAD', 'OPTIONS')
                     and request.blueprint in ('objects_admin', 'requirements_admin')))
    # Returning from impersonation must remain possible even without admin access.
    if request.path in ('/api/admin/impersonate/stop', '/api/admin/impersonate/status'):
        return None
    if protected and current_user.is_authenticated and not current_user.can_view_admin():
        return jsonify(error='Нет доступа к админ-панели'), 403

app.register_blueprint(dashboard_bp)
from routes.candidate_rates import candidate_rates_bp
app.register_blueprint(candidate_rates_bp)
app.register_blueprint(planned_departures_bp)
app.register_blueprint(service_reports_bp)
app.register_blueprint(report_refresh_bp)
app.register_blueprint(selection_bp)
app.register_blueprint(admin_pages_bp)
app.register_blueprint(objects_admin_bp)
app.register_blueprint(requirements_admin_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(worker_status_bp)
app.register_blueprint(faq_bp)

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
        if not current_user.can_view_admin():
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

@app.route('/reports')
@login_required
def reports_page():
    if not current_user.can_view_reports():
        return render_template('no_access.html',
                               message='У вас нет доступа к отчётам',
                               return_url='/welcome'), 403
    return render_template('reports.html')


@app.route('/service')
@login_required
def service_page():
    if not current_user.can_view_vip():
        return render_template('no_access.html',
                               message='У вас нет доступа к разделу VIP',
                               return_url='/welcome'), 403
    today = get_moscow_date()
    return render_template('service.html', today=today, month_start=today[:8] + '01')

@app.route('/faq')
@login_required
def faq_page():
    """Страница часто задаваемых вопросов - руководство пользователя"""
    return render_template('faq_new.html')

@app.route('/worker-status')
@login_required
def worker_status_page():
    """Страница статусов вахтовиков"""
    try:
        if not current_user.can_view_worker_status():
            return render_template('no_access.html', 
                                 message="У вас нет доступа к этой странице",
                                 return_url="/welcome"), 403
        return render_template('worker_status.html')
    except Exception as e:
        logger.error(f"Ошибка при загрузке worker_status_page: {e}", exc_info=True)
        return render_template('no_access.html', 
                             message="Произошла ошибка при загрузке страницы",
                             return_url="/welcome"), 500

# ========== ДИАГНОСТИЧЕСКИЙ ЭНДПОИНТ ==========
@app.route('/api/debug/upload-limit', methods=['GET'])
def debug_upload_limit():
    import os
    route_sheets_dir = os.path.join(app.root_path, 'static', 'uploads', 'route_sheets')
    files = []
    if os.path.exists(route_sheets_dir):
        files = os.listdir(route_sheets_dir)
    return jsonify({
        'max_content_length': app.config.get('MAX_CONTENT_LENGTH', 'not set'),
        'max_content_length_mb': app.config.get('MAX_CONTENT_LENGTH', 0) / 1024 / 1024,
        'route_sheets_files': files
    })

# ========== ФОНДОВАЯ ЗАДАЧА ДЛЯ ЕЖЕДНЕВНОГО СНИПШОТА ==========

def generate_daily_snapshot():
    """Генерирует снапшот за прошедший день (запускается в 20:00 МСК)"""
    from database import save_daily_snapshots_batch, get_plan_requirements_for_date, delete_snapshots_for_date
    from datetime import timedelta
    
    # Инициализируем таблицу, если её нет (на всякий случай)
    init_daily_snapshots_table()
    
    # Берём вчерашний день
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    logger.info(f"🔄 Запуск фоновой генерации снапшота за {yesterday}")
    
    try:
        target_date = datetime.strptime(yesterday, '%Y-%m-%d')
        offices_stats = bitrix_api.get_all_offices_stats(target_date)
        plans = get_plan_requirements_for_date(target_date)
        
        delete_snapshots_for_date(yesterday)
        
        snapshots = []
        
        for office_name, office_data in offices_stats.items():
            for obj_name, count in office_data.get('objects', {}).items():
                plan_info = plans.get(obj_name, {})
                snapshots.append({
                    'object_name': obj_name,
                    'office_name': office_name,
                    'count': count,
                    'plan': plan_info.get('count', 0),
                    'is_high': plan_info.get('is_high', False)
                })
        
        for obj_name, plan_info in plans.items():
            already_added = any(s['object_name'] == obj_name for s in snapshots)
            if not already_added:
                snapshots.append({
                    'object_name': obj_name,
                    'office_name': 'complect',
                    'count': 0,
                    'plan': plan_info.get('count', 0),
                    'is_high': plan_info.get('is_high', False)
                })
        
        if snapshots:
            save_daily_snapshots_batch(yesterday, snapshots)
            logger.info(f"✅ Снапшот за {yesterday} сохранён ({len(snapshots)} записей)")
        else:
            logger.warning(f"⚠️ Нет данных для снапшота за {yesterday}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при генерации снапшота: {e}", exc_info=True)


# ========== ФОНОВЫЕ ЗАДАЧИ ==========
scheduler = BackgroundScheduler()
scheduler.add_job(func=cleanup_old_records, trigger="cron", hour=3, minute=0, args=[30], 
                  id='cleanup_database')
scheduler.add_job(func=cleanup_old_unused_avatars, trigger="cron", hour=3, minute=30, 
                  id='cleanup_avatars')

# Добавляем задачу для ежедневного снапшота (каждый день в 20:00)
try:
    scheduler.add_job(
        func=generate_daily_snapshot,
        trigger='cron',
        hour=20,
        minute=0,
        id='daily_snapshot'
    )
    logger.info("✅ Запланирована ежедневная генерация снапшотов в 20:00")
except Exception as e:
    logger.warning(f"⚠️ Не удалось запланировать задачу снапшотов: {e}")

# Добавляем задачу для очистки старых записей вахтовиков (старше 365 дней)
try:
    from database.worker_status import delete_old_worker_records
    scheduler.add_job(
        func=delete_old_worker_records,
        trigger='cron',
        hour=3,
        minute=15,
        args=[365],
        id='cleanup_worker_statuses'
    )
    logger.info("✅ Запланирована очистка старых записей вахтовиков (старше 365 дней)")
except Exception as e:
    logger.warning(f"⚠️ Не удалось запланировать очистку вахтовиков: {e}")

scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ========== ФУНКЦИЯ ДЛЯ АВТОМАТИЧЕСКОГО ЗАПУСКА МИГРАЦИЙ ==========

def run_migrations_if_needed():
    """Запускает миграции при старте приложения (если venv доступен)"""
    import os
    import subprocess
    
    # Проверяем, есть ли виртуальное окружение
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    
    if os.path.exists(venv_python):
        try:
            result = subprocess.run(
                [venv_python, "run_migration.py"],
                cwd=os.path.dirname(__file__),
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info("✅ Миграции проверены/применены")
            else:
                logger.warning(f"⚠️ Проблема с миграциями: {result.stderr}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось запустить миграции: {e}")
    else:
        logger.info("ℹ️ Виртуальное окружение не найдено, пропускаем миграции")

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
    # Запускаем миграции при старте
    run_migrations_if_needed()
    
    logger.info("🚀 Запуск объединённого CRM Dashboard...")
    logger.info(f"🕐 Московское время: {get_moscow_now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("📊 Дашборд использует план из БД (вакансии)")
    logger.info("🎯 Подбор объектов использует текущие потребности (без привязки к дате)")
    logger.info("📋 Паспорта объектов доступны в админ-панели")
    logger.info(f"📦 Максимальный размер загружаемого файла: {app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024} MB")
    logger.info("📸 Ежедневные снапшоты генерируются в 20:00")
    logger.info("❓ FAQ - руководство пользователя доступно по адресу /faq")
    logger.info("👥 Статусы вахтовиков доступны по адресу /worker-status")
    logger.info("📊 Отчёты по 1 смене доступны в дашборде (вкладки '1 смена по объектам' и '1 смена по сотрудникам')")
    logger.info("⭕️ Системный администратор может обнулять потребности объектов (кнопка в управлении потребностью)")
    debug_mode = FLASK_ENV == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=5001)
