// Публичная страница руководства пользователя.
(function () {
    let articles = [];
    let currentCategory = 'all';
    const icons = { start: '🚀', dashboard: '📊', selection: '🎯', workers: '👥', admin: '⚙️', profile: '👤' };
    const safe = value => String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');

    async function loadFaq() {
        try {
            const response = await fetch('/api/faq', { credentials: 'include' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка загрузки');
            articles = data.articles || [];
            renderCategories();
            renderArticles();
        } catch (error) {
            document.getElementById('faqList').innerHTML = `<div class="faq-empty">❌ ${safe(error.message)}</div>`;
        }
    }

    function renderCategories() {
        const categories = [];
        articles.forEach(article => {
            if (!categories.some(item => item.slug === article.category_slug)) categories.push({ slug: article.category_slug, title: article.category_title });
        });
        document.getElementById('faqCategories').innerHTML = `<button class="category-btn active" data-category="all">Все разделы</button>${categories.map(category => `<button class="category-btn" data-category="${safe(category.slug)}">${icons[category.slug] || '📘'} ${safe(category.title)}</button>`).join('')}`;
        document.querySelectorAll('.category-btn').forEach(button => button.addEventListener('click', () => {
            currentCategory = button.dataset.category;
            document.querySelectorAll('.category-btn').forEach(item => item.classList.toggle('active', item === button));
            renderArticles();
        }));
    }

    function renderBlock(block) {
        if (block.type === 'text') return `<p>${safe(block.content).replace(/\n/g, '<br>')}</p>`;
        if (block.type === 'note') return `<div class="faq-note"><strong>Важно:</strong> ${safe(block.content).replace(/\n/g, '<br>')}</div>`;
        if (block.type === 'list' || block.type === 'steps') {
            const tag = block.type === 'steps' ? 'ol' : 'ul';
            const items = String(block.content || '').split('\n').map(item => item.trim()).filter(Boolean);
            return `<${tag}>${items.map(item => `<li>${safe(item)}</li>`).join('')}</${tag}>`;
        }
        if (block.type === 'image' && block.url) return `<figure class="faq-image"><img src="${safe(block.url)}" alt="${safe(block.caption || 'Скриншот инструкции')}" loading="lazy" onclick="openFaqImage(this.src)">${block.caption ? `<figcaption>${safe(block.caption)}</figcaption>` : ''}</figure>`;
        return '';
    }

    function renderArticles() {
        const filtered = currentCategory === 'all' ? articles : articles.filter(article => article.category_slug === currentCategory);
        const container = document.getElementById('faqList');
        if (!filtered.length) return void (container.innerHTML = '<div class="faq-empty">В этом разделе пока нет материалов</div>');
        container.innerHTML = filtered.map(article => `<article class="faq-item"><button class="faq-question" type="button"><span>${safe(article.title)}</span><i class="fas fa-chevron-right"></i></button><div class="faq-answer">${(article.blocks || []).map(renderBlock).join('')}</div></article>`).join('');
        container.querySelectorAll('.faq-question').forEach(button => button.addEventListener('click', () => button.closest('.faq-item').classList.toggle('open')));
    }

    window.openFaqImage = function (src) {
        const overlay = document.createElement('div');
        overlay.className = 'faq-lightbox';
        const image = document.createElement('img');
        image.src = src;
        image.alt = 'Увеличенный скриншот';
        overlay.appendChild(image);
        overlay.addEventListener('click', () => overlay.remove());
        document.body.appendChild(overlay);
    };

    document.addEventListener('DOMContentLoaded', loadFaq);
})();
