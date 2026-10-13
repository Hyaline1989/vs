"""Add the departments FAQ or explicitly refresh its outdated wording."""
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
    {'type': 'note', 'content': 'Сотрудник без отдела после назначения получает права выбранного отдела. Если сотрудника переводят из другого отдела, его текущие доступы сохраняются как личные исключения. Само открытие карточки сотрудника ничего не меняет.'},
    {'type': 'text', 'content': 'Где посмотреть состав отдела\nВыберите отдел. В блоке «Сотрудники отдела» появятся список участников, их количество и поиск по имени.'},
    {'type': 'text', 'content': 'Как убрать сотрудника из отдела\nНажмите «Убрать из отдела» напротив имени и подтвердите действие.'},
    {'type': 'note', 'content': 'Аккаунт не удаляется. Текущие доступы сохраняются как личные настройки и больше не зависят от прежнего отдела.'},
    {'type': 'text', 'content': 'Сотрудники без отдела\nВ блоке «Без отдела» показаны сотрудники с индивидуальными правами. Они действуют, пока сотрудника не назначили в отдел. После назначения начинают действовать права отдела; при необходимости личные исключения можно настроить отдельно.'},
    {'type': 'text', 'content': 'Как настроить особый доступ одному сотруднику\nВ блоке «Доступ сотрудника» выберите человека. Для состоящих в отделе доступны три варианта:'},
    {'type': 'list', 'content': '«Как у отдела» — использовать общие настройки отдела.\n«Разрешить» — открыть доступ лично этому сотруднику.\n«Запретить» — закрыть доступ лично этому сотруднику.'},
    {'type': 'text', 'content': 'Нажмите «Сохранить исключения». У сотрудника без отдела выберите «Разрешить» или «Запретить» и нажмите «Сохранить индивидуальные права».'},
    {'type': 'note', 'content': 'Разрешение отдельного объекта не открывает закрытый раздел «Подбор объектов».'},
    {'type': 'text', 'content': 'Чем роль отличается от отдела\nОтдел определяет доступные разделы и объекты. Роль определяет полномочия внутри приложения.'},
    {'type': 'text', 'content': 'Перевод в другой отдел не меняет роль. Название отдела «Руководители» само по себе не назначает роль руководителя. Администраторы сохраняют полный доступ независимо от настроек отделов.'},
    {'type': 'text', 'content': 'Как изменить роль\nТолько системный администратор может выбрать другую роль в карточке существующего пользователя. Свою роль изменить нельзя. После смены роли обновите страницу пользователя, чтобы увидеть новые полномочия.'},
    {'type': 'note', 'content': 'Создавать пользователей могут администраторы. В форме добавления нового пользователя настройка отдела появляется только после сохранения его карточки.'},
]

REPLACEMENTS = {
    'При обычном назначении в отдел прежние права сотрудника сохраняются как личные исключения. Это касается и доступа к объектам. Само открытие карточки сотрудника ничего не меняет.': BLOCKS[6]['content'],
    'Сотрудники без отдела\nВ блоке «Без отдела» показаны сотрудники со старыми индивидуальными правами. Они продолжают действовать, пока сотрудника не назначили в отдел. Выберите сотрудника, чтобы посмотреть или изменить его доступы.': next(block['content'] for block in BLOCKS if block['content'].startswith('Сотрудники без отдела\n')),
}
OBSOLETE_BLOCK = 'Как применить права отдела вместо личных\nВыберите сотрудника, уже назначенного в отдел, и нажмите «Применить права отдела». Вектор покажет, какие доступы к разделам и объектам изменятся. Проверьте список и только затем подтвердите действие. Личные исключения будут удалены.'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--update-existing', action='store_true', help='Update only the existing departments article')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    if not args.apply:
        print('No changes. Use --apply to add the article or --apply --update-existing to refresh it.')
        return
    if args.update_existing:
        with closing(sqlite3.connect(str(path))) as conn:
            row = conn.execute('SELECT id,blocks_json FROM faq_articles WHERE title=?', (TITLE,)).fetchone()
            if not row:
                raise ValueError('Departments FAQ article not found')
            old_blocks = json.loads(row[1])
            updated = [dict(block, content=REPLACEMENTS[block['content']]) if block['content'] in REPLACEMENTS
                       else block for block in old_blocks if block['content'] != OBSOLETE_BLOCK]
            if updated == old_blocks:
                print('Article is already current; no changes.')
                return
            if not any(block['content'] in REPLACEMENTS for block in old_blocks) and not any(block['content'] == OBSOLETE_BLOCK for block in old_blocks):
                raise ValueError('Old wording not found; review this article manually')
            backup = path.with_name(path.name + '.departments-faq-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
            with closing(sqlite3.connect(str(backup))) as copy:
                conn.backup(copy)
            with conn:
                cursor = conn.execute('UPDATE faq_articles SET blocks_json=? WHERE id=? AND blocks_json=?',
                                      (json.dumps(updated, ensure_ascii=False), row[0], row[1]))
                if cursor.rowcount != 1:
                    raise ValueError('Article changed during update; no changes saved')
            print('Article updated:', row[0])
            print('Backup:', backup.name)
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
