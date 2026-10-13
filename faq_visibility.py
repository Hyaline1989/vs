"""Role-based visibility for published FAQ articles."""


def visible_faq_articles(articles, role):
    if role == 'admin':
        return articles
    hidden = {'admin', 'reports'}
    if role == 'agent':
        hidden.add('dashboard')
    return [article for article in articles if article['category_slug'] not in hidden]
