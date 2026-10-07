"""Explicit, additive FAQ update. Existing articles are never overwritten."""
import argparse
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

TITLE = 'Отделы и права доступа'
BLOCKS = [
    {'type': 'text', 'content': 'У каждого сотрудника может быть один отдел. Отдел определяет, какие разделы Вектора и объекты доступны сотруднику. Управлять отделами могут администраторы.'},
    {'type': 'text', 'content': 'Как создать отдел'},
    {'type': 'steps', 'content': 'Откройте «Админ-панель → Отделы и исключения».\nВыберите «Создать новый отдел» и введите название.\nОтметьте доступные разделы.\nВыберите объекты для подбора или включите «Все объекты, включая новые».\nНажмите «Сохранить отдел».'},
    {'type': 'note', 'content': 'Разделы без доступа скрыты в верхнем меню и на стартовой странице. После изменения прав обновите страницу.'},
    {'type': 'text', 'content': 'Как добавить или перевести сотрудника'},
    {'type': 'steps', 'content': 'Выберите нужный отдел.\nВ блоке «Сотрудники отдела» нажмите «Добавить сотрудников».\nОтметьте нужных людей.\nНажмите «Назначить выбранных» и подтвердите действие.'},
    {'type': 'note', 'content': 'Сотрудник получит права выбранного отдела. При переводе прежние личные исключения сбрасываются.'},
    {'type': 'text', 'content': 'Где посмотреть состав отдела\nВыберите отдел. В блоке «Сотрудники отдела» появятся список участников, их количество и поиск по имени.'},
    {'type': 'text', 'content': 'Как убрать сотрудника из отдела\nНажмите «Убрать из отдела» напротив имени и подтвердите действие.'},
    {'type': 'note', 'content': 'Аккаунт не удаляется. Текущие доступы сохраняются как личные настройки и больше не зависят от прежнего отдела.'},
    {'type': 'text', 'content': 'Как настроить особый доступ одному сотруднику\nВ блоке «Личные исключения» выберите сотрудника. Для разделов и объектов доступны три варианта:'},
    {'type': 'list', 'content': '«Как у отдела» — использовать общие настройки отдела.\n«Разрешить» — открыть доступ лично этому сотруднику.\n«Запретить» — закрыть доступ лично этому сотруднику.'},
    {'type': 'text', 'content': 'Нажмите «Сохранить исключения». Чтобы убрать все личные исключения у сотрудника, состоящего в отделе, нажмите «Использовать только права отдела».'},
    {'type': 'note', 'content': 'Разрешение отдельного объекта не открывает закрытый раздел «Подбор объектов».'},
    {'type': 'text', 'content': 'Чем роль отличается от отдела\nОтдел определяет доступные разделы и объекты. Роль определяет полномочия внутри приложения.'},
    {'type': 'text', 'content': 'Перевод в другой отдел не меняет роль. Название отдела «Руководители» само по себе не назначает роль руководителя. Администраторы сохраняют полный доступ независимо от настроек отделов.'},
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    if not args.apply:
        print('No changes. Use --apply to add the article.')
        return
    with closing(sqlite3.connect(str(path))) as conn, conn:
        if conn.execute('SELECT id FROM faq_articles WHERE title=?', (TITLE,)).fetchone():
            print('Article already exists; no changes.')
            return
        backup = path.with_name(path.name + '.departments-faq-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        with closing(sqlite3.connect(str(backup))) as copy:
            conn.backup(copy)
        conn.execute('BEGIN IMMEDIATE')
        # Recheck inside the write transaction to avoid a concurrent duplicate.
        if conn.execute('SELECT id FROM faq_articles WHERE title=?', (TITLE,)).fetchone():
            print('Article already exists; no changes.')
            return
        before = conn.execute('SELECT * FROM faq_articles ORDER BY id').fetchall()
        category = conn.execute('SELECT category_title,category_order FROM faq_articles WHERE category_slug=? ORDER BY id LIMIT 1', ('admin',)).fetchone()
        category = category or ('Администрирование', 5)
        order = conn.execute('SELECT COALESCE(MAX(sort_order),0)+1 FROM faq_articles WHERE category_slug=?', ('admin',)).fetchone()[0]
        cursor = conn.execute('INSERT INTO faq_articles(category_slug,category_title,title,blocks_json,category_order,sort_order,is_published) VALUES(?,?,?,?,?,?,1)', ('admin', category[0], TITLE, json.dumps(BLOCKS, ensure_ascii=False), category[1], order))
        article_id = cursor.lastrowid
        after = conn.execute('SELECT * FROM faq_articles WHERE id<>? ORDER BY id', (article_id,)).fetchall()
        assert before == after, 'Existing FAQ articles changed'
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        print('Article added:', article_id)
        print('Existing articles unchanged:', len(before))
        print('Backup:', backup.name)


if __name__ == '__main__':
    main()
