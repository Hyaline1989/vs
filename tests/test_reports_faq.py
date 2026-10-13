"""Report FAQ update checks without touching the application database."""
import json
import sqlite3
import unittest

from faq_reports_content import REPORT_FAQ_ARTICLES
from scripts.add_reports_faq import apply_changes


class ReportsFaqTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.execute('''CREATE TABLE faq_articles (
            id INTEGER PRIMARY KEY,
            category_slug TEXT,
            category_title TEXT,
            title TEXT,
            blocks_json TEXT,
            category_order INTEGER,
            sort_order INTEGER,
            is_published INTEGER DEFAULT 1
        )''')
        self.conn.execute('INSERT INTO faq_articles VALUES (1,?,?,?,?,?,?,1)',
                          ('dashboard', 'Дашборд', 'Как скачать отчёт План/Факт', '[]', 2, 1))
        self.conn.execute('INSERT INTO faq_articles VALUES (2,?,?,?,?,?,?,1)',
                          ('selection', 'Подбор объектов', 'Личная статья', '[{"type":"text","content":"Сохранить"}]', 3, 1))
        self.conn.commit()

    def test_adds_each_report_and_preserves_other_articles(self):
        personal_before = self.conn.execute('SELECT * FROM faq_articles WHERE id=2').fetchone()
        self.assertEqual(apply_changes(self.conn), (1, 6))
        self.assertEqual(self.conn.execute('SELECT * FROM faq_articles WHERE id=2').fetchone(), personal_before)
        articles = self.conn.execute("SELECT title,blocks_json FROM faq_articles WHERE category_slug='reports' ORDER BY sort_order").fetchall()
        self.assertEqual([title for title, _ in articles], [title for title, _ in REPORT_FAQ_ARTICLES])
        self.assertTrue(all(json.loads(blocks) for _, blocks in articles))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM faq_articles WHERE title='Как скачать отчёт План/Факт'").fetchone()[0], 0)
        self.assertEqual(apply_changes(self.conn), (0, 0))


if __name__ == '__main__':
    unittest.main()
