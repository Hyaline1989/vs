"""FAQ categories are filtered before they reach the browser."""
import unittest

from faq_visibility import visible_faq_articles


class FaqVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.articles = [{'category_slug': slug} for slug in
                         ('start', 'dashboard', 'selection', 'workers', 'admin', 'reports', 'profile')]

    def categories_for(self, role):
        return [item['category_slug'] for item in visible_faq_articles(self.articles, role)]

    def test_administrator_sees_every_category(self):
        self.assertEqual(self.categories_for('admin'), [item['category_slug'] for item in self.articles])

    def test_manager_and_viewer_do_not_see_admin_or_reports(self):
        for role in ('manager', 'viewer'):
            with self.subTest(role=role):
                categories = self.categories_for(role)
                self.assertIn('dashboard', categories)
                self.assertNotIn('admin', categories)
                self.assertNotIn('reports', categories)

    def test_agent_also_does_not_see_dashboard(self):
        categories = self.categories_for('agent')
        self.assertEqual(categories, ['start', 'selection', 'workers', 'profile'])

    def test_unknown_role_cannot_see_administrative_categories(self):
        categories = self.categories_for('unknown')
        self.assertNotIn('admin', categories)
        self.assertNotIn('reports', categories)


if __name__ == '__main__':
    unittest.main()
