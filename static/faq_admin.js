// Редактор руководства FAQ в админ-панели.
let faqAdminArticles = [];
let faqEditingId = null;
let faqEditingBlocks = [];

const FAQ_CATEGORIES = {
    start: 'Начало работы',
    dashboard: 'Дашборд',
    reports: 'Отчёты',
    selection: 'Подбор объектов',
    workers: 'Вахтовики',
    admin: 'Администрирование',
    profile: 'Личный кабинет'
};
const FAQ_CATEGORY_ORDER = Object.keys(FAQ_CATEGORIES);

async function loadFaqAdmin() {
    const container = document.getElementById('faqAdminContainer');
    if (!container) return;
    container.innerHTML = '<div class="loading">Загрузка статей...</div>';
    try {
        const response = await fetch('/api/admin/faq', { credentials: 'include' });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Не удалось загрузить FAQ');
        faqAdminArticles = data.articles || [];
        renderFaqAdmin();
    } catch (error) {
        container.innerHTML = `<div class="error-state">❌ ${escapeHtml(error.message)}</div>`;
    }
}

function renderFaqAdmin() {
    const container = document.getElementById('faqAdminContainer');
    if (!container) return;
    if (!faqAdminArticles.length) {
        container.innerHTML = '<div class="no-data">Статей пока нет</div>';
        return;
    }
    const groups = new Map();
    faqAdminArticles.forEach(article => {
        const key = `${article.category_order}:${article.category_slug}`;
        if (!groups.has(key)) groups.set(key, { title: article.category_title, articles: [] });
        groups.get(key).articles.push(article);
    });
    container.innerHTML = Array.from(groups.values()).map(group => `
        <section class="faq-admin-group">
            <h4>${escapeHtml(group.title)}</h4>
            ${group.articles.map(article => `
                <div class="faq-admin-row ${article.is_published ? '' : 'is-hidden'}">
                    <div class="faq-admin-order">${article.sort_order}</div>
                    <div class="faq-admin-name"><strong>${escapeHtml(article.title)}</strong>${article.is_published ? '' : '<span class="faq-draft-badge">Скрыта</span>'}</div>
                    <div class="faq-admin-actions">
                        <button class="action-btn edit-btn" onclick="openFaqArticleEditor(${article.id})" title="Редактировать"><i class="fas fa-edit"></i></button>
                        <button class="action-btn delete-btn" onclick="deleteFaqArticle(${article.id})" title="Удалить"><i class="fas fa-trash"></i></button>
                    </div>
                </div>`).join('')}
        </section>`).join('');
}

function openFaqArticleEditor(articleId = null) {
    const article = articleId ? faqAdminArticles.find(item => item.id === articleId) : null;
    faqEditingId = article?.id || null;
    faqEditingBlocks = JSON.parse(JSON.stringify(article?.blocks || [{ type: 'text', content: '' }]));
    document.getElementById('faqArticleModal')?.remove();
    const modal = document.createElement('div');
    modal.id = 'faqArticleModal';
    modal.className = 'modal faq-editor-modal';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3><i class="fas fa-book-open"></i> ${article ? 'Редактировать статью' : 'Добавить статью'}</h3>
                <button class="modal-close" onclick="closeFaqArticleEditor()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="faqArticleForm" onsubmit="event.preventDefault(); saveFaqArticle();">
                    <div class="form-row faq-order-row">
                        <div class="form-group"><label>Раздел *</label><select id="faqCategorySlug" onchange="syncFaqCategoryTitle()">${Object.entries(FAQ_CATEGORIES).map(([slug, title]) => `<option value="${slug}">${title}</option>`).join('')}</select></div>
                        <div class="form-group"><label>Порядок раздела</label><input id="faqCategoryOrder" type="number" min="1" value="1"></div>
                        <div class="form-group"><label>Порядок статьи</label><input id="faqSortOrder" type="number" min="1" value="1"></div>
                    </div>
                    <input id="faqCategoryTitle" type="hidden">
                    <div class="form-group"><label>Название статьи *</label><input id="faqArticleTitle" type="text" required></div>
                    <div class="form-group checkbox"><label><input id="faqPublished" type="checkbox" checked><span>Показывать статью пользователям</span></label></div>
                    <div class="faq-block-toolbar">
                        <strong>Содержание статьи</strong>
                        <div>
                            <button type="button" class="btn-small" onclick="addFaqBlock('text')">+ Текст</button>
                            <button type="button" class="btn-small" onclick="addFaqBlock('list')">+ Список</button>
                            <button type="button" class="btn-small" onclick="addFaqBlock('steps')">+ Шаги</button>
                            <button type="button" class="btn-small" onclick="addFaqBlock('note')">+ Примечание</button>
                            <button type="button" class="btn-small" onclick="addFaqBlock('image')">+ Скриншот</button>
                        </div>
                    </div>
                    <div id="faqBlocksEditor"></div>
                    <div class="form-actions"><button type="button" class="btn-cancel" onclick="closeFaqArticleEditor()">Отмена</button><button type="submit" class="btn-save">Сохранить статью</button></div>
                </form>
            </div>
        </div>`;
    document.body.appendChild(modal);
    document.getElementById('faqCategorySlug').value = article?.category_slug || 'start';
    document.getElementById('faqCategoryTitle').value = article?.category_title || FAQ_CATEGORIES.start;
    document.getElementById('faqCategoryOrder').value = article?.category_order || 1;
    document.getElementById('faqSortOrder').value = article?.sort_order || 1;
    document.getElementById('faqArticleTitle').value = article?.title || '';
    document.getElementById('faqPublished').checked = article ? article.is_published : true;
    renderFaqBlocksEditor();
}

function syncFaqCategoryTitle() {
    const slug = document.getElementById('faqCategorySlug').value;
    document.getElementById('faqCategoryTitle').value = FAQ_CATEGORIES[slug] || slug;
    const orders = faqAdminArticles
        .filter(article => article.category_slug === slug)
        .map(article => Number(article.category_order))
        .filter(Number.isFinite);
    const counts = new Map();
    orders.forEach(order => counts.set(order, (counts.get(order) || 0) + 1));
    const existingOrder = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || a - b)[0];
    document.getElementById('faqCategoryOrder').value = existingOrder || Math.max(1, FAQ_CATEGORY_ORDER.indexOf(slug) + 1);
}

function renderFaqBlocksEditor() {
    const container = document.getElementById('faqBlocksEditor');
    if (!container) return;
    const labels = { text: 'Текст', list: 'Маркированный список', steps: 'Пошаговый список', note: 'Важное примечание', image: 'Скриншот' };
    container.innerHTML = faqEditingBlocks.map((block, index) => {
        const controls = `<button type="button" onclick="moveFaqBlock(${index}, -1)" title="Выше">↑</button><button type="button" onclick="moveFaqBlock(${index}, 1)" title="Ниже">↓</button><button type="button" class="danger" onclick="removeFaqBlock(${index})" title="Удалить">×</button>`;
        if (block.type === 'image') {
            return `<div class="faq-block-editor" data-index="${index}"><div class="faq-block-editor-head"><strong>${labels[block.type]}</strong><div>${controls}</div></div>${block.url ? `<img class="faq-block-preview" src="${escapeHtml(block.url)}" alt="">` : ''}<input type="hidden" class="faq-block-url" value="${escapeHtml(block.url || '')}"><input type="file" accept=".png,.jpg,.jpeg,.jfif,.webp,image/jpeg" onchange="uploadFaqImage(${index}, this)"><input type="text" class="faq-block-caption" value="${escapeHtml(block.caption || '')}" placeholder="Подпись к изображению"></div>`;
        }
        return `<div class="faq-block-editor" data-index="${index}"><div class="faq-block-editor-head"><strong>${labels[block.type]}</strong><div>${controls}</div></div><textarea class="faq-block-content" rows="${block.type === 'text' ? 4 : 5}" placeholder="${block.type === 'text' ? 'Введите текст' : 'Каждый пункт с новой строки'}">${escapeHtml(block.content || '')}</textarea></div>`;
    }).join('');
}

function collectFaqBlocks() {
    document.querySelectorAll('#faqBlocksEditor .faq-block-editor').forEach((element, index) => {
        const block = faqEditingBlocks[index];
        if (block.type === 'image') {
            block.url = element.querySelector('.faq-block-url')?.value || '';
            block.caption = element.querySelector('.faq-block-caption')?.value.trim() || '';
        } else {
            block.content = element.querySelector('.faq-block-content')?.value.trim() || '';
        }
    });
}

function addFaqBlock(type) { collectFaqBlocks(); faqEditingBlocks.push(type === 'image' ? { type, url: '', caption: '' } : { type, content: '' }); renderFaqBlocksEditor(); }
function removeFaqBlock(index) { collectFaqBlocks(); faqEditingBlocks.splice(index, 1); renderFaqBlocksEditor(); }
function moveFaqBlock(index, direction) {
    collectFaqBlocks();
    const target = index + direction;
    if (target < 0 || target >= faqEditingBlocks.length) return;
    [faqEditingBlocks[index], faqEditingBlocks[target]] = [faqEditingBlocks[target], faqEditingBlocks[index]];
    renderFaqBlocksEditor();
}

async function uploadFaqImage(index, input) {
    const file = input.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('image', file);
    input.disabled = true;
    try {
        const response = await fetch('/api/admin/faq/images', { method: 'POST', credentials: 'include', body: formData });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Ошибка загрузки');
        collectFaqBlocks();
        faqEditingBlocks[index].url = data.url;
        renderFaqBlocksEditor();
        showNotification('✅ Скриншот загружен', 'success');
    } catch (error) {
        showNotification(`❌ ${error.message}`, 'error');
        input.disabled = false;
    }
}

async function saveFaqArticle() {
    collectFaqBlocks();
    const payload = {
        category_slug: document.getElementById('faqCategorySlug').value,
        category_title: document.getElementById('faqCategoryTitle').value,
        category_order: Number(document.getElementById('faqCategoryOrder').value) || 1,
        sort_order: Number(document.getElementById('faqSortOrder').value) || 1,
        title: document.getElementById('faqArticleTitle').value.trim(),
        is_published: document.getElementById('faqPublished').checked,
        blocks: faqEditingBlocks.filter(block => block.type === 'image' ? block.url : block.content)
    };
    if (!payload.title) return showNotification('❌ Укажите название статьи', 'error');
    const url = faqEditingId ? `/api/admin/faq/${faqEditingId}` : '/api/admin/faq';
    try {
        const response = await fetch(url, { method: faqEditingId ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(payload) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Ошибка сохранения');
        closeFaqArticleEditor();
        await loadFaqAdmin();
        showNotification('✅ Статья сохранена', 'success');
    } catch (error) { showNotification(`❌ ${error.message}`, 'error'); }
}

async function deleteFaqArticle(articleId) {
    const article = faqAdminArticles.find(item => item.id === articleId);
    if (!confirm(`Удалить статью «${article?.title || ''}»?`)) return;
    try {
        const response = await fetch(`/api/admin/faq/${articleId}`, { method: 'DELETE', credentials: 'include' });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Ошибка удаления');
        await loadFaqAdmin();
        showNotification('✅ Статья удалена', 'success');
    } catch (error) { showNotification(`❌ ${error.message}`, 'error'); }
}

function closeFaqArticleEditor() { document.getElementById('faqArticleModal')?.remove(); faqEditingId = null; faqEditingBlocks = []; }

Object.assign(window, { loadFaqAdmin, openFaqArticleEditor, closeFaqArticleEditor, syncFaqCategoryTitle, addFaqBlock, removeFaqBlock, moveFaqBlock, uploadFaqImage, saveFaqArticle, deleteFaqArticle });
