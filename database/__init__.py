# database/__init__.py
# -*- coding: utf-8 -*-
"""
Модуль базы данных - фасад
Все функции импортируются отсюда для обратной совместимости
"""

from database.db_core import DB_NAME, get_db_connection, init_db

# Инициализация таблиц (все функции init_* теперь в db_core)
from database.db_core import (
    init_objects_settings,
    init_vacancy_tables,
    init_current_requirements_table,
    init_passports_table,
    init_daily_snapshots_table
)

# Пользователи и права
from database.users import (
    get_user_by_id,
    get_user_by_username,
    get_all_users,
    create_user,
    update_user,
    delete_user,
    hard_delete_user,
    is_system_admin,
    get_user_module_permissions,
    set_user_module_permission,
    get_user_object_permissions,
    set_user_object_permission,
    grant_all_objects_access,
    log_user_action,
    update_user_profile,
    change_user_password,
    get_user_avatar,
    save_user_avatar,
    delete_user_avatar,
    cleanup_old_unused_avatars,
    cleanup_old_records
)

# Объекты
from database.objects import (
    get_objects_settings,
    get_objects_settings_extended,
    get_object_by_id,
    update_object_settings,
    update_object_settings_full,
    create_object_extended,
    delete_object,
    get_global_order,
    save_global_order,
    get_object_passport,
    save_object_passport,
    update_route_sheet,
    get_route_sheet_filename,
    delete_route_sheet
)

# Текущие потребности (для подбора объектов)
from database.requirements import (
    get_current_requirements,
    get_current_requirements_for_object,
    save_current_requirements
)

# Вакансии (план на дату для дашборда)
from database.vacancy import (
    get_all_vacancy_data,
    get_plan_requirements_for_date,
    save_vacancy_object,
    delete_vacancy_object,
    save_vacancy_position,
    delete_vacancy_position,
    save_vacancy_requirements_batch
)

# Снапшоты
from database.snapshots import (
    save_daily_snapshot,
    save_daily_snapshots_batch,
    get_snapshot_report,
    check_snapshot_exists,
    delete_snapshots_for_date
)

__all__ = [
    # core
    'DB_NAME', 'get_db_connection', 'init_db',
    'init_objects_settings', 'init_vacancy_tables',
    'init_current_requirements_table', 'init_passports_table',
    'init_daily_snapshots_table',
    
    # users
    'get_user_by_id', 'get_user_by_username', 'get_all_users',
    'create_user', 'update_user', 'delete_user', 'hard_delete_user',
    'is_system_admin', 'get_user_module_permissions',
    'set_user_module_permission', 'get_user_object_permissions',
    'set_user_object_permission', 'grant_all_objects_access',
    'log_user_action', 'update_user_profile', 'change_user_password',
    'get_user_avatar', 'save_user_avatar', 'delete_user_avatar',
    'cleanup_old_unused_avatars', 'cleanup_old_records',
    
    # objects
    'get_objects_settings', 'get_objects_settings_extended',
    'get_object_by_id', 'update_object_settings',
    'update_object_settings_full', 'create_object_extended',
    'delete_object', 'get_global_order', 'save_global_order',
    'get_object_passport', 'save_object_passport',
    'update_route_sheet', 'get_route_sheet_filename', 'delete_route_sheet',
    
    # requirements
    'get_current_requirements', 'get_current_requirements_for_object',
    'save_current_requirements',
    
    # vacancy
    'get_all_vacancy_data', 'get_plan_requirements_for_date',
    'save_vacancy_object', 'delete_vacancy_object',
    'save_vacancy_position', 'delete_vacancy_position',
    'save_vacancy_requirements_batch',
    
    # snapshots
    'save_daily_snapshot', 'save_daily_snapshots_batch',
    'get_snapshot_report', 'check_snapshot_exists',
    'delete_snapshots_for_date'
]