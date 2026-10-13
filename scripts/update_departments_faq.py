"""Update only the original departments FAQ article, with an explicit --apply."""
import argparse
from contextlib import closing
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3

from add_departments_faq import BLOCKS, TITLE

ORIGINAL_HASH = '9e058bfd445d85d99c726a6fc6485ea8704a536511d6f1b8b52400902a152f4c'


def fingerprint(blocks):
    return hashlib.sha256(json.dumps(blocks, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description='Обновить описание отделов в FAQ')
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true', help='Сохранить обновление в базе')
    args = parser.parse_args()
    path = Path(args.database).resolve(strict=True)
    target_hash = fingerprint(BLOCKS)

    if not args.apply:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
            rows = conn.execute('SELECT id,blocks_json FROM faq_articles WHERE title=?', (TITLE,)).fetchall()
            if len(rows) != 1:
                raise SystemExit('Нужна ровно одна статья FAQ «Отделы и права доступа». База не изменена.')
            current_hash = fingerprint(json.loads(rows[0][1]))
        print(f'Статья ID {rows[0][0]}: ', end='')
        if current_hash == target_hash:
            print('уже актуальна. База не изменена.')
        elif current_hash == ORIGINAL_HASH:
            print('найдена исходная версия; обновление возможно. База не изменена.')
        else:
            print('отредактирована вручную. Автоматическое обновление остановлено; база не изменена.')
        return

    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute('SELECT id,blocks_json FROM faq_articles WHERE title=?', (TITLE,)).fetchall()
        if len(rows) != 1:
            raise SystemExit('Нужна ровно одна статья FAQ. Ничего не изменено.')
        article_id, current_json = rows[0]
        current_hash = fingerprint(json.loads(current_json))
        if current_hash == target_hash:
            print('Статья уже актуальна. Ничего не изменено.')
            return
        if current_hash != ORIGINAL_HASH:
            raise SystemExit('Статья отредактирована вручную. Автоматическое обновление отменено.')

        backup = path.with_name(path.name + '.faq-access-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
        with closing(sqlite3.connect(str(backup))) as copy:
            conn.backup(copy)
        try:
            conn.execute('BEGIN IMMEDIATE')
            latest = conn.execute('SELECT blocks_json FROM faq_articles WHERE id=?', (article_id,)).fetchone()
            if not latest or fingerprint(json.loads(latest[0])) != ORIGINAL_HASH:
                raise ValueError('Статья изменилась после проверки. Обновление отменено.')
            old_other = conn.execute('SELECT * FROM faq_articles WHERE id<>? ORDER BY id', (article_id,)).fetchall()
            conn.execute('UPDATE faq_articles SET blocks_json=? WHERE id=?', (json.dumps(BLOCKS, ensure_ascii=False), article_id))
            if conn.execute('SELECT * FROM faq_articles WHERE id<>? ORDER BY id', (article_id,)).fetchall() != old_other:
                raise ValueError('Другие статьи изменились. Обновление отменено.')
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Ошибка проверки базы. Обновление отменено.')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        print(f'Обновлена статья FAQ ID {article_id}. Другие статьи не изменены.')
        print('Резервная копия:', backup.name)


if __name__ == '__main__':
    main()
