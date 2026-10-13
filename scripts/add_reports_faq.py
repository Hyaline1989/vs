"""Add the six Reports FAQ articles and remove obsolete Plan/Fact download help."""
import argparse
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from faq_reports_content import REPORT_FAQ_ARTICLES


OLD_TITLE = 'Как скачать отчёт План/Факт'


def apply_changes(conn):
    conn.execute('BEGIN IMMEDIATE')
    try:
        removed = conn.execute('DELETE FROM faq_articles WHERE category_slug=? AND title=?',
                               ('dashboard', OLD_TITLE)).rowcount
        existing = conn.execute('SELECT category_order FROM faq_articles WHERE category_slug=? LIMIT 1',
                                ('reports',)).fetchone()
        category_order = existing[0] if existing else conn.execute(
            'SELECT COALESCE(MAX(category_order),0)+1 FROM faq_articles').fetchone()[0]
        sort_order = conn.execute('SELECT COALESCE(MAX(sort_order),0) FROM faq_articles WHERE category_slug=?',
                                  ('reports',)).fetchone()[0]
        added = 0
        for title, blocks in REPORT_FAQ_ARTICLES:
            if conn.execute('SELECT 1 FROM faq_articles WHERE category_slug=? AND title=?',
                            ('reports', title)).fetchone():
                continue
            sort_order += 1
            conn.execute('''INSERT INTO faq_articles
                (category_slug,category_title,title,blocks_json,category_order,sort_order,is_published)
                VALUES (?,?,?,?,?,?,1)''',
                ('reports', 'Отчёты', title, json.dumps(blocks, ensure_ascii=False),
                 category_order, sort_order))
            added += 1
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Проверка целостности базы не пройдена')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return removed, added


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    with closing(sqlite3.connect(str(path))) as conn:
        old_count = conn.execute('SELECT COUNT(*) FROM faq_articles WHERE category_slug=? AND title=?',
                                 ('dashboard', OLD_TITLE)).fetchone()[0]
        new_count = sum(bool(conn.execute('SELECT 1 FROM faq_articles WHERE category_slug=? AND title=?',
                                           ('reports', title)).fetchone())
                        for title, _ in REPORT_FAQ_ARTICLES)
        if not old_count and new_count == len(REPORT_FAQ_ARTICLES):
            print('FAQ уже обновлён; изменений нет.')
            return
        if not args.apply:
            print(f'Проверка: убрать статей: {old_count}; добавить статей: {len(REPORT_FAQ_ARTICLES) - new_count}. Для обновления добавьте --apply.')
            return
        backup = path.with_name(path.name + '.before-reports-faq-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        with closing(sqlite3.connect(str(backup))) as copy:
            conn.backup(copy)
        removed, added = apply_changes(conn)
        print(f'FAQ обновлён: удалено {removed}, добавлено {added} статей.')
        print('Резервная копия:', backup)


if __name__ == '__main__':
    main()
