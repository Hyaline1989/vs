# config.py - полная версия с существующим источником
# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# ========== ОБЩИЕ НАСТРОЙКИ ==========
# Основной цвет
PRIMARY_COLOR = "#A42C30"

# Секретный ключ для Flask (обязательно из переменных окружения)
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY не установлен в переменных окружения!")

# ========== ПРОЕКТ 1: Bitrix24 API ==========
BITRIX_WEBHOOK_URL = os.environ.get('BITRIX_WEBHOOK_URL')
if not BITRIX_WEBHOOK_URL:
    raise ValueError("BITRIX_WEBHOOK_URL не установлен в переменных окружения!")

# Поля Bitrix24
FIELD_DATE_DIRECTED = "UF_CRM_1684488775220"  # Дата направлен на объект
FIELD_COMPANY = "UF_CRM_642A972B79B02"        # Объект (компания)

# Источники (SOURCE_ID)
SOURCE_POTOK = "UC_IV7KE7"                    # Поток
SOURCE_GORKIY52 = "UC_TUXCUX"                 # Проект В2Б
SOURCE_BISHKEK = "REPEAT_SALE"                # Подбор Бишкек
SOURCE_AGENT = "UC_3HKPIP"                    # Агент
SOURCE_PEREVAHTOVKA = "UC_5LI24O"             # Перевахтовка
SOURCE_REFERRAL = "UC_1S4DWZ"                 # Приведи друга

# Источник для направлений из CRM (используем существующий источник Агент)
SOURCE_CRM_DIRECTION = SOURCE_AGENT

# Все офисы для фильтрации
ALL_OFFICES = [
    SOURCE_POTOK,
    SOURCE_GORKIY52,
    SOURCE_BISHKEK,
    SOURCE_AGENT
]

# Исключаемые источники
EXCLUDED_SOURCES = [SOURCE_PEREVAHTOVKA, SOURCE_REFERRAL]

# ========== ПРОЕКТ 1: Google Sheets (только для справки, не используется) ==========
GOOGLE_SHEET_ID = "1M2uFFMmSHcbQHSqRW3D2oBjayfdyHuRIBC68Y64uQhI"
GOOGLE_SHEET_GID = "1372231628"
GOOGLE_SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid={GOOGLE_SHEET_GID}"

# ========== ОПТИМИЗИРОВАННЫЕ НАСТРОЙКИ RATE LIMITING ==========
RATE_LIMIT_AUTH = "10 per minute"
RATE_LIMIT_DEFAULT = "1000 per day;200 per hour"
RATE_LIMIT_DASHBOARD = "300 per minute"
RATE_LIMIT_REPORT = "30 per minute"
RATE_LIMIT_SELECTION = "150 per minute"
RATE_LIMIT_ADMIN = "50 per minute"

# ========== ВРЕМЯ ОБНОВЛЕНИЯ ==========
GOOGLE_SHEETS_UPDATE_INTERVAL_MINUTES = 15
GOOGLE_SHEETS_UPDATE_INTERVAL_SECONDS = 900

# ========== АВТОРИЗАЦИЯ ==========
SESSION_DURATION_HOURS = 12

# ========== ПРАВИЛА СОПОСТАВЛЕНИЯ ==========
OBJECT_MATCHING_RULES = {
    'Спортмастер': ['спортмастер', 'спортмастер (москва)', 'спортмастер москва'],
    'Спортмастер СПБ': ['спортмастер спб', 'спортмастер санкт-петербург', 'спортмастер питер'],
    'Мираторг': ['мираторг', 'мираторг (брянск)', 'мираторг брянск'],
    'Мираторг Тула': ['мираторг тула', 'мираторг (тула)'],
    'Major': ['major', 'мэйджор', 'мажор'],
    'СДТ': ['сдт', 'сдт (москва)', 'сдт москва'],
    'METRO MGL': ['metro', 'метро', 'metro mgl'],
    'Цветы Раменское': ['цветы раменское', 'цветы', 'раменское'],
    'Яндекс Тарный': ['яндекс', 'яндекс тарный', 'тарный'],
}

# ========== REDIS НАСТРОЙКИ ДЛЯ RATE LIMITING ==========
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
REDIS_SOCKET_TIMEOUT = 5
REDIS_SOCKET_CONNECT_TIMEOUT = 5

# ========== БЕЗОПАСНОСТЬ ==========
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')

# Разрешённые origin для CORS
if FLASK_ENV == 'development':
    ALLOWED_ORIGINS = [
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ]
else:
    ALLOWED_ORIGINS = [
        "https://complect.org",
        "https://www.complect.org",
        "http://complect.org",
        "http://www.complect.org",
        "https://vs.complect.org",
        "https://www.vs.complect.org",
        "http://vs.complect.org",
        "http://www.vs.complect.org",
        "http://147.45.184.173:5000",
        "https://147.45.184.173:5000",
        "http://147.45.184.173",
        "https://147.45.184.173",
    ]

MAX_CONTENT_LENGTH = 1 * 1024 * 1024
BITRIX_TIMEOUT = 30
GOOGLE_SHEETS_TIMEOUT = 30

# ========== ПРОЕКТ 2: База объектов ==========
# Базовая структура объектов с разделением на РФ и СНГ
OBJECTS_BASE = [
    {"id": 1, "name": "Сберлогистика Пушкино", "ageMin": 18, "ageMax": 45, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ"], 
     "allowsConviction": False, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1671362639#gid=1671362639"},
    {"id": 2, "name": "СДТ", "ageMin": 18, "ageMax": 55, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=807193246#gid=807193246"},
    {"id": 3, "name": "Креветки Клинский", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ", "СНГ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=2035276078#gid=2035276078"},
    {"id": 4, "name": "Major", "ageMin": 18, "ageMax": 55, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": False, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1066301663#gid=1066301663"},
    {"id": 5, "name": "Спортмастер", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ"], 
     "allowsConviction": False, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=2015665303#gid=2015665303"},
    {"id": 6, "name": "METRO MGL", "ageMin": 18, "ageMax": 45, 
     "allowedGenders": ["мужчина"], "allowedNationalities": ["РФ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=2037581346#gid=2037581346"},
    {"id": 7, "name": "Клинский мясокомбинат", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ", "СНГ"], 
     "allowsConviction": False, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=484336549#gid=484336549"},
    {"id": 8, "name": "Цветы Раменское", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1489900442#gid=1489900442"},
    {"id": 9, "name": "Агама Лешково", "ageMin": 25, "ageMax": 45, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=371889370#gid=371889370"},
    {"id": 10, "name": "ФитнесШок", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1609895640#gid=1609895640"},
    {"id": 11, "name": "Тамбовский бекон", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=2134096102#gid=2134096102"},
    {"id": 12, "name": "Павловская Птицефабрика", "ageMin": 18, "ageMax": 55, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ", "СНГ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=459944799#gid=459944799"},
    {"id": 13, "name": "АртПак", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1786219261#gid=1786219261"},
    {"id": 14, "name": "Мяснов", "ageMin": 18, "ageMax": 55, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": False, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=912447009#gid=912447009"},
    {"id": 15, "name": "Мираторг", "ageMin": 18, "ageMax": 55, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": False, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1137221797#gid=1137221797"},
    {"id": 16, "name": "Мираторг Тула", "ageMin": 18, "ageMax": 55, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1209986820#gid=1209986820"},
    {"id": 17, "name": "БелГранКорм Новгород", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=2042428287#gid=2042428287"},
    {"id": 18, "name": "Индейка Калуга", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=478943669#gid=478943669"},
    {"id": 19, "name": "Спортмастер СПБ", "ageMin": 18, "ageMax": 45, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ"], 
     "allowsConviction": False, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1368572665#gid=1368572665"},
    {"id": 20, "name": "КуулКлевер", "ageMin": 18, "ageMax": 55, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["СНГ"], 
     "allowsConviction": False, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1379171118#gid=1379171118"},
    {"id": 21, "name": "Яндекс Тарный", "ageMin": 18, "ageMax": 45, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ"], 
     "allowsConviction": False, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=244932662#gid=244932662"},
    {"id": 22, "name": "Мармеладыч", "ageMin": 18, "ageMax": 50, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ", "СНГ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=1707924363#gid=1707924363"},
    {"id": 23, "name": "Невский кондитер", "ageMin": 18, "ageMax": 55, 
     "allowedGenders": ["мужчина", "женщина"], "allowedNationalities": ["РФ", "РБ", "СНГ"], 
     "allowsConviction": True, "link": "https://docs.google.com/spreadsheets/d/13FLpkCRuY8Bhdq8VzAsUMXlH-O6DcnwMlb3a1d82z44/edit?gid=401397030#gid=401397030"}
]