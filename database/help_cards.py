# database/help_cards.py
# -*- coding: utf-8 -*-
import json
import logging
import sqlite3

from database.db_core import DB_NAME

logger = logging.getLogger(__name__)


DEFAULT_CIS_HELP_CARD = {
    'sections': [
        {
            'title': 'Белоруссия',
            'checklist': [
                'Паспорт (1 стр, 2 стр, регистрация с Белоруссии)',
                'СНИЛС (если есть)',
                'ИНН (если есть)',
                'Реквизиты (если есть)',
                'Регистрация временная (если есть)'
            ],
            'documents': []
        },
        {
            'title': 'Киргизия/Казахстан',
            'checklist': [],
            'documents': [
                {'title': 'Загранпаспорт Казахстан', 'note': '', 'image_url': ''},
                {'title': 'ID карта Казахстан', 'note': '', 'image_url': ''},
                {'title': 'Загранпаспорт Киргизия', 'note': '', 'image_url': ''}
            ]
        }
    ]
}


def _normalize_card_payload(payload):
    if not isinstance(payload, dict):
        payload = {}

    sections = payload.get('sections', [])
    if not isinstance(sections, list):
        sections = []

    clean_sections = []
    for section in sections:
        if not isinstance(section, dict):
            continue

        checklist = section.get('checklist', [])
        if isinstance(checklist, str):
            checklist = [line.strip() for line in checklist.splitlines() if line.strip()]
        elif not isinstance(checklist, list):
            checklist = []

        documents = section.get('documents', [])
        if not isinstance(documents, list):
            documents = []

        clean_documents = []
        for document in documents:
            if not isinstance(document, dict):
                continue
            clean_documents.append({
                'title': str(document.get('title', '')).strip(),
                'note': str(document.get('note', '')).strip(),
                'image_url': str(document.get('image_url', '')).strip()
            })

        clean_sections.append({
            'title': str(section.get('title', '')).strip(),
            'checklist': [str(item).strip() for item in checklist if str(item).strip()],
            'documents': clean_documents
        })

    return {'sections': clean_sections}


def get_help_card(slug):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM help_cards WHERE slug = ?', (slug,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {
                'slug': slug,
                'title': 'Документы для СНГ',
                'sourceUrl': '',
                'content': DEFAULT_CIS_HELP_CARD
            }

        data = dict(row)
        try:
            content = json.loads(data.get('content_json') or '{}')
        except json.JSONDecodeError:
            content = {}

        return {
            'slug': data['slug'],
            'title': data['title'],
            'sourceUrl': data.get('source_url') or '',
            'content': _normalize_card_payload(content),
            'updatedAt': data.get('updated_at')
        }
    except Exception as e:
        logger.error(f"Ошибка при получении шпаргалки {slug}: {e}")
        return None


def save_help_card(slug, title, content, source_url='', updated_by=None):
    try:
        title = (title or '').strip() or 'Документы для СНГ'
        normalized_content = _normalize_card_payload(content)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO help_cards (slug, title, content_json, source_url, updated_by)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                content_json = excluded.content_json,
                source_url = excluded.source_url,
                updated_by = excluded.updated_by,
                updated_at = CURRENT_TIMESTAMP
        ''', (
            slug,
            title,
            json.dumps(normalized_content, ensure_ascii=False),
            source_url or '',
            updated_by
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении шпаргалки {slug}: {e}")
        return False
