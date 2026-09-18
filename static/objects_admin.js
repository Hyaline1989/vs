// static/objects_admin.js
// Управление объектами в админ-панели

// ========== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ БЕЗОПАСНОГО HTML ==========
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: white;
        padding: 12px 20px;
        border-radius: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        z-index: 10001;
        border-left: 4px solid ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#A42C30'};
        animation: slideIn 0.3s ease;
    `;
    document.body.appendChild(notification);
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

let objectsList = [];
let isEditingObject = false;
let currentEditObjectId = null;

// ========== ЗАГРУЗКА ОБЪЕКТОВ ==========
async function loadObjects() {
    const container = document.getElementById('objectsTableContainer');
    if (!container) return;
    
    container.innerHTML = '<div class="loading">Загрузка объектов...</div>';
    
    try {
        const response = await fetch('/api/admin/objects', { credentials: 'include' });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        objectsList = data.objects || [];
        renderObjectsTable(objectsList);
        
        // Обновляем количество объектов
        const countEl = document.getElementById('objectsCount');
        if (countEl) countEl.textContent = objectsList.length;
        
    } catch (error) {
        console.error('Ошибка загрузки объектов:', error);
        container.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>Не удалось загрузить объекты</p>
                <button onclick="loadObjects()" class="retry-btn">Повторить</button>
            </div>
        `;
    }
}

function renderObjectsTable(objects) {
    const container = document.getElementById('objectsTableContainer');
    if (!container) return;
    
    if (!objects || objects.length === 0) {
        container.innerHTML = '<div class="empty-state">Нет объектов</div>';
        return;
    }
    
    const isMobile = window.innerWidth <= 768;
    
    if (isMobile) {
        // Карточки для мобильных
        let html = '<div class="objects-cards">';
        
        for (const obj of objects) {
            const visibleIcon = obj.visible ? 'fa-eye' : 'fa-eye-slash';
            const visibleText = obj.visible ? 'Видим' : 'Скрыт';
            
            html += `
                <div class="object-card" data-object-id="${obj.id}">
                    <div class="object-card-header">
                        <div class="object-card-name">
                            <strong>${escapeHtml(obj.name)}</strong>
                        </div>
                        <div class="object-card-status">
                            <span class="visibility-badge ${obj.visible ? 'visible' : 'hidden'}">
                                <i class="fas ${visibleIcon}"></i> ${visibleText}
                            </span>
                        </div>
                    </div>
                    <div class="object-card-info">
                        <div><i class="fas fa-calendar-alt"></i> Возраст: ${obj.ageMin} - ${obj.ageMax} лет</div>
                        <div><i class="fas fa-venus-mars"></i> Пол: ${obj.allowedGenders?.join(', ') || '-'}</div>
                        <div><i class="fas fa-globe"></i> Гражданство: ${obj.allowedNationalities?.join(', ') || '-'}</div>
                        <div><i class="fas fa-gavel"></i> Судимость: ${obj.allowsConviction ? 'Разрешена' : 'Запрещена'}</div>
                        ${obj.region ? `<div><i class="fas fa-map-marker-alt"></i> Регион: ${escapeHtml(obj.region)}</div>` : ''}
                    </div>
                    <div class="object-card-actions">
                        <button class="action-btn edit-btn" onclick="editObject(${obj.id})" title="Редактировать">
                            <i class="fas fa-edit"></i> Редактировать
                        </button>
                        <button class="action-btn passport-btn" onclick="editObjectPassport(${obj.id}, '${escapeHtml(obj.name)}')" title="Паспорт объекта">
                            <i class="fas fa-id-card"></i> Паспорт
                        </button>
                        <button class="action-btn delete-btn" onclick="deleteObject(${obj.id})" title="Удалить">
                            <i class="fas fa-trash"></i> Удалить
                        </button>
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        container.innerHTML = html;
        return;
    }
    
    // Таблица для десктопа
    let html = `
        <table class="objects-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Название</th>
                    <th>Возраст</th>
                    <th>Пол</th>
                    <th>Гражданство</th>
                    <th>Судимость</th>
                    <th>Регион</th>
                    <th>Видимость</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    for (const obj of objects) {
        const visibleIcon = obj.visible ? 'fa-eye' : 'fa-eye-slash';
        const visibleClass = obj.visible ? 'visible' : 'hidden';
        
        html += `
            <tr data-object-id="${obj.id}">
                <td>${obj.id}</td>
                <td><strong>${escapeHtml(obj.name)}</strong></td>
                <td>${obj.ageMin} - ${obj.ageMax}</td>
                <td>${obj.allowedGenders?.join(', ') || '-'}</td>
                <td>${obj.allowedNationalities?.join(', ') || '-'}</td>
                <td>${obj.allowsConviction ? '<span class="allowed">Разрешена</span>' : '<span class="forbidden">Запрещена</span>'}</td>
                <td>${escapeHtml(obj.region || '-')}</td>
                <td><span class="visibility-badge ${visibleClass}"><i class="fas ${visibleIcon}"></i> ${obj.visible ? 'Видим' : 'Скрыт'}</span></td>
                <td class="actions-cell">
                    <button class="action-btn edit-btn" onclick="editObject(${obj.id})" title="Редактировать"><i class="fas fa-edit"></i></button>
                    <button class="action-btn passport-btn" onclick="editObjectPassport(${obj.id}, '${escapeHtml(obj.name)}')" title="Паспорт объекта"><i class="fas fa-id-card"></i></button>
                    <button class="action-btn delete-btn" onclick="deleteObject(${obj.id})" title="Удалить"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `;
    }
    
    html += `</tbody></table>`;
    container.innerHTML = html;
}

// ========== ОТКРЫТИЕ МОДАЛЬНОГО ОКНА ДЛЯ ДОБАВЛЕНИЯ ==========
function openAddObjectModal() {
    isEditingObject = false;
    currentEditObjectId = null;
    
    document.getElementById('objectModalTitle').textContent = 'Добавить объект';
    document.getElementById('objectForm').reset();
    document.getElementById('objectId').value = '';
    const positionGroup = document.getElementById('objPositionGroup');
    const positionInput = document.getElementById('objPosition');
    if (positionGroup) positionGroup.style.display = 'block';
    if (positionInput) {
        positionInput.value = '';
        positionInput.required = true;
    }
    
    // Устанавливаем значения по умолчанию
    document.getElementById('objAgeMin').value = '18';
    document.getElementById('objAgeMax').value = '55';
    document.querySelectorAll('input[name="objAllowedGender"]').forEach(checkbox => {
        checkbox.checked = true;
    });
    document.querySelectorAll('input[name="objAllowedNationality"]').forEach(checkbox => {
        checkbox.checked = checkbox.value === 'РФ';
    });
    document.getElementById('objAllowsConviction').checked = false;
    document.getElementById('objStrictLaborCode').checked = false;
    document.getElementById('objVisible').checked = true;
    document.getElementById('objRegion').value = '';
    
    document.getElementById('objectModal').style.display = 'flex';
}

// ========== РЕДАКТИРОВАНИЕ ОБЪЕКТА ==========
async function editObject(objectId) {
    const obj = objectsList.find(o => o.id === objectId);
    if (!obj) return;
    
    isEditingObject = true;
    currentEditObjectId = objectId;
    
    document.getElementById('objectModalTitle').textContent = 'Редактировать объект';
    document.getElementById('objectId').value = objectId;
    document.getElementById('objName').value = obj.name || '';
    const positionGroup = document.getElementById('objPositionGroup');
    const positionInput = document.getElementById('objPosition');
    if (positionGroup) positionGroup.style.display = 'none';
    if (positionInput) {
        positionInput.value = '';
        positionInput.required = false;
    }
    document.getElementById('objAgeMin').value = obj.ageMin || 18;
    document.getElementById('objAgeMax').value = obj.ageMax || 55;
    const allowedGenders = new Set(obj.allowedGenders || []);
    document.querySelectorAll('input[name="objAllowedGender"]').forEach(checkbox => {
        checkbox.checked = allowedGenders.has(checkbox.value);
    });
    const allowedNationalities = new Set(obj.allowedNationalities || []);
    document.querySelectorAll('input[name="objAllowedNationality"]').forEach(checkbox => {
        checkbox.checked = allowedNationalities.has(checkbox.value);
    });
    document.getElementById('objAllowsConviction').checked = obj.allowsConviction || false;
    document.getElementById('objStrictLaborCode').checked = obj.strictLaborCode || false;
    document.getElementById('objVisible').checked = obj.visible !== false;
    document.getElementById('objRegion').value = obj.region || '';
    
    document.getElementById('objectModal').style.display = 'flex';
}

// ========== РЕДАКТИРОВАНИЕ ПАСПОРТА ОБЪЕКТА ==========
function editObjectPassport(objectId, objectName) {
    // Открываем редактор паспорта (функция из passport_editor.js)
    if (typeof openPassportEditor === 'function') {
        openPassportEditor(objectId, objectName);
    } else {
        console.error('passport_editor.js не загружен');
        showNotification('Ошибка: редактор паспорта не загружен', 'error');
    }
}

// ========== СОХРАНЕНИЕ ОБЪЕКТА ==========
async function saveObject() {
    const form = document.getElementById('objectForm');
    const saveButton = form?.querySelector('button[type="submit"]');

    // Prevent duplicate requests while the server is processing the first one.
    if (form?.dataset.saving === 'true') {
        return;
    }

    const objectId = document.getElementById('objectId').value;
    const name = document.getElementById('objName').value.trim();
    const positionName = document.getElementById('objPosition')?.value.trim() || '';
    const ageMin = parseInt(document.getElementById('objAgeMin').value);
    const ageMax = parseInt(document.getElementById('objAgeMax').value);
    const allowedGenders = Array.from(
        document.querySelectorAll('input[name="objAllowedGender"]:checked')
    ).map(checkbox => checkbox.value);
    const allowedNationalities = Array.from(
        document.querySelectorAll('input[name="objAllowedNationality"]:checked')
    ).map(checkbox => checkbox.value);
    const allowsConviction = document.getElementById('objAllowsConviction').checked;
    const strictLaborCode = document.getElementById('objStrictLaborCode').checked;
    const visible = document.getElementById('objVisible').checked;
    const region = document.getElementById('objRegion').value.trim();
    
    // Валидация
    if (!name) {
        showNotification('❌ Введите название объекта', 'error');
        return;
    }

    if (!objectId && !positionName) {
        showNotification('❌ Введите должность', 'error');
        return;
    }
    
    if (isNaN(ageMin) || ageMin < 18 || ageMin > 100) {
        showNotification('❌ Минимальный возраст должен быть от 18 до 100', 'error');
        return;
    }
    
    if (isNaN(ageMax) || ageMax < ageMin) {
        showNotification('❌ Максимальный возраст должен быть больше минимального', 'error');
        return;
    }
    
    if (allowedGenders.length === 0) {
        showNotification('❌ Укажите хотя бы один допустимый пол', 'error');
        return;
    }
    
    if (allowedNationalities.length === 0) {
        showNotification('❌ Укажите хотя бы одно допустимое гражданство', 'error');
        return;
    }
    
    const data = {
        name,
        ageMin,
        ageMax,
        allowedGenders,
        allowedNationalities,
        allowsConviction,
        strictLaborCode,
        visible,
        region
    };

    if (!objectId) {
        data.positionName = positionName;
    }
    
    try {
        if (form) form.dataset.saving = 'true';
        if (saveButton) saveButton.disabled = true;

        let url, method;
        if (objectId) {
            url = `/api/admin/objects/${objectId}`;
            method = 'PUT';
        } else {
            url = '/api/admin/objects';
            method = 'POST';
        }
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            showNotification('✅ Объект сохранён', 'success');
            closeObjectModal();
            loadObjects();
        } else {
            if (form) delete form.dataset.saving;
            if (saveButton) saveButton.disabled = false;
            const error = await response.json();
            showNotification('❌ ' + (error.error || 'Ошибка сохранения'), 'error');
        }
    } catch (error) {
        if (form) delete form.dataset.saving;
        if (saveButton) saveButton.disabled = false;
        console.error('Ошибка сохранения:', error);
        showNotification('❌ Ошибка сохранения', 'error');
    }
}

// ========== УДАЛЕНИЕ ОБЪЕКТА ==========
async function deleteObject(objectId) {
    const obj = objectsList.find(o => o.id === objectId);
    if (!obj) return;
    
    if (!confirm(`Вы уверены, что хотите удалить объект "${obj.name}"?\n\nЭто действие нельзя отменить.`)) return;
    
    try {
        const response = await fetch(`/api/admin/objects/${objectId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (response.ok) {
            showNotification('✅ Объект удалён', 'success');
            loadObjects();
        } else {
            const error = await response.json();
            showNotification('❌ ' + (error.error || 'Ошибка удаления'), 'error');
        }
    } catch (error) {
        console.error('Ошибка удаления:', error);
        showNotification('❌ Ошибка удаления', 'error');
    }
}

// ========== ФИЛЬТРАЦИЯ ОБЪЕКТОВ ==========
function filterObjects() {
    const searchTerm = document.getElementById('searchObjects')?.value.toLowerCase() || '';
    const visibilityFilter = document.getElementById('filterVisibility')?.value || 'all';
    
    const container = document.getElementById('objectsTableContainer');
    if (!container) return;
    
    const isMobile = window.innerWidth <= 768;
    
    if (isMobile) {
        const cards = document.querySelectorAll('.object-card');
        cards.forEach(card => {
            const name = card.querySelector('.object-card-name strong')?.textContent.toLowerCase() || '';
            const visibilityBadge = card.querySelector('.visibility-badge')?.textContent.toLowerCase() || '';
            
            let matches = true;
            
            if (searchTerm && !name.includes(searchTerm)) {
                matches = false;
            }
            
            if (visibilityFilter !== 'all') {
                const isVisible = visibilityBadge.includes('видим');
                if (visibilityFilter === 'visible' && !isVisible) matches = false;
                if (visibilityFilter === 'hidden' && isVisible) matches = false;
            }
            
            card.style.display = matches ? '' : 'none';
        });
    } else {
        const rows = document.querySelectorAll('#objectsTableContainer tbody tr');
        rows.forEach(row => {
            const name = row.cells[1]?.textContent.toLowerCase() || '';
            const visibilityCell = row.cells[7]?.textContent.toLowerCase() || '';
            
            let matches = true;
            
            if (searchTerm && !name.includes(searchTerm)) {
                matches = false;
            }
            
            if (visibilityFilter !== 'all') {
                const isVisible = visibilityCell.includes('видим');
                if (visibilityFilter === 'visible' && !isVisible) matches = false;
                if (visibilityFilter === 'hidden' && isVisible) matches = false;
            }
            
            row.style.display = matches ? '' : 'none';
        });
    }
}

// ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
function closeObjectModal() {
    document.getElementById('objectModal').style.display = 'none';
}

// ========== РЕДАКТОР ШПАРГАЛКИ "ДОКУМЕНТЫ СНГ" ==========
let cisHelpCardData = null;

async function openCisDocumentsEditor() {
    let modal = document.getElementById('cisDocumentsEditorModal');
    if (modal) modal.remove();

    modal = document.createElement('div');
    modal.id = 'cisDocumentsEditorModal';
    modal.className = 'modal modal-large';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content cis-editor-modal">
            <div class="modal-header">
                <h3><i class="fas fa-passport"></i> Документы СНГ</h3>
                <button class="modal-close" onclick="closeCisDocumentsEditor()">&times;</button>
            </div>
            <div class="modal-body">
                <div id="cisDocumentsEditorBody" class="cis-editor-body">
                    <div class="loading">Загрузка шпаргалки...</div>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    await loadCisDocumentsEditor();
}

function closeCisDocumentsEditor() {
    const modal = document.getElementById('cisDocumentsEditorModal');
    if (modal) modal.remove();
}

async function loadCisDocumentsEditor() {
    const container = document.getElementById('cisDocumentsEditorBody');
    if (!container) return;

    try {
        const response = await fetch('/api/admin/objects/help-cards/cis-documents', { credentials: 'include' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        cisHelpCardData = await response.json();
        renderCisDocumentsEditor();
    } catch (error) {
        console.error('Ошибка загрузки шпаргалки:', error);
        container.innerHTML = '<div class="error-state">Не удалось загрузить шпаргалку</div>';
    }
}

function renderCisDocumentsEditor() {
    const container = document.getElementById('cisDocumentsEditorBody');
    if (!container || !cisHelpCardData) return;

    const sections = cisHelpCardData.content?.sections || [];
    container.innerHTML = `
        <div class="cis-editor-top">
            <div class="form-group">
                <label>Заголовок</label>
                <input type="text" id="cisHelpTitle" value="${escapeHtml(cisHelpCardData.title || 'Документы для СНГ')}" autocomplete="off">
            </div>
            <div class="form-group">
                <label>Ссылка на исходный Google Docs</label>
                <input type="url" id="cisHelpSourceUrl" value="${escapeHtml(cisHelpCardData.sourceUrl || '')}" autocomplete="off" placeholder="https://docs.google.com/...">
            </div>
        </div>
        <div id="cisSectionsEditor">
            ${sections.map((section, index) => renderCisSectionEditor(section, index)).join('')}
        </div>
        <div class="cis-editor-actions">
            <button type="button" class="btn-cancel" onclick="addCisSection()"><i class="fas fa-plus"></i> Добавить раздел</button>
            <button type="button" class="btn-save" onclick="saveCisDocumentsHelpCard()"><i class="fas fa-save"></i> Сохранить шпаргалку</button>
        </div>
    `;
}

function renderCisSectionEditor(section, index) {
    const checklist = Array.isArray(section.checklist) ? section.checklist.join('\n') : '';
    const documents = Array.isArray(section.documents) ? section.documents : [];

    return `
        <div class="cis-edit-section" data-section-index="${index}">
            <div class="cis-edit-section-header">
                <input type="text" class="cis-section-title" value="${escapeHtml(section.title || '')}" placeholder="Название раздела, например Белоруссия">
                <button type="button" class="action-btn delete-btn" onclick="removeCisSection(${index})" title="Удалить раздел"><i class="fas fa-trash"></i></button>
            </div>
            <div class="form-group">
                <label>Список документов</label>
                <textarea class="cis-section-checklist" rows="5" placeholder="Каждый пункт с новой строки">${escapeHtml(checklist)}</textarea>
            </div>
            <div class="cis-documents-editor">
                <div class="cis-documents-editor-title">Примеры документов с картинками</div>
                <div class="cis-document-list">
                    ${documents.map((documentItem, docIndex) => renderCisDocumentEditor(documentItem, index, docIndex)).join('')}
                </div>
                <button type="button" class="btn-cancel" onclick="addCisDocument(${index})"><i class="fas fa-plus"></i> Добавить документ</button>
            </div>
        </div>
    `;
}

function renderCisDocumentEditor(documentItem, sectionIndex, docIndex) {
    const imageUrl = documentItem.image_url || '';
    return `
        <div class="cis-document-edit" data-doc-index="${docIndex}">
            <div class="cis-document-fields">
                <input type="text" class="cis-document-title" value="${escapeHtml(documentItem.title || '')}" placeholder="Название документа">
                <textarea class="cis-document-note" rows="2" placeholder="Комментарий или что проверить">${escapeHtml(documentItem.note || '')}</textarea>
                <input type="hidden" class="cis-document-image-url" value="${escapeHtml(imageUrl)}">
                <div class="cis-image-upload-row">
                    <input type="file" accept="image/*" onchange="uploadCisDocumentImage(this)">
                    ${imageUrl ? `<a href="${escapeHtml(imageUrl)}" target="_blank">Открыть картинку</a>` : '<span class="cis-muted">Картинка не загружена</span>'}
                </div>
            </div>
            <div class="cis-document-preview">
                ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="">` : '<div class="cis-image-placeholder">Нет картинки</div>'}
                <button type="button" class="action-btn delete-btn" onclick="removeCisDocument(${sectionIndex}, ${docIndex})" title="Удалить документ"><i class="fas fa-trash"></i></button>
            </div>
        </div>
    `;
}

function collectCisDocumentsEditorData() {
    const sections = [];
    document.querySelectorAll('#cisSectionsEditor .cis-edit-section').forEach(sectionEl => {
        const title = sectionEl.querySelector('.cis-section-title')?.value.trim() || '';
        const checklistText = sectionEl.querySelector('.cis-section-checklist')?.value || '';
        const checklist = checklistText.split('\n').map(item => item.trim()).filter(Boolean);
        const documents = [];

        sectionEl.querySelectorAll('.cis-document-edit').forEach(docEl => {
            const docTitle = docEl.querySelector('.cis-document-title')?.value.trim() || '';
            const note = docEl.querySelector('.cis-document-note')?.value.trim() || '';
            const imageUrl = docEl.querySelector('.cis-document-image-url')?.value.trim() || '';

            if (docTitle || note || imageUrl) {
                documents.push({ title: docTitle, note, image_url: imageUrl });
            }
        });

        if (title || checklist.length || documents.length) {
            sections.push({ title, checklist, documents });
        }
    });

    return {
        title: document.getElementById('cisHelpTitle')?.value.trim() || 'Документы для СНГ',
        sourceUrl: document.getElementById('cisHelpSourceUrl')?.value.trim() || '',
        content: { sections }
    };
}

function refreshCisHelpDataFromForm() {
    cisHelpCardData = {
        ...(cisHelpCardData || {}),
        ...collectCisDocumentsEditorData()
    };
}

function addCisSection() {
    refreshCisHelpDataFromForm();
    if (!cisHelpCardData.content) cisHelpCardData.content = { sections: [] };
    cisHelpCardData.content.sections.push({ title: '', checklist: [], documents: [] });
    renderCisDocumentsEditor();
}

function removeCisSection(index) {
    refreshCisHelpDataFromForm();
    cisHelpCardData.content.sections.splice(index, 1);
    renderCisDocumentsEditor();
}

function addCisDocument(sectionIndex) {
    refreshCisHelpDataFromForm();
    const section = cisHelpCardData.content.sections[sectionIndex];
    if (!section.documents) section.documents = [];
    section.documents.push({ title: '', note: '', image_url: '' });
    renderCisDocumentsEditor();
}

function removeCisDocument(sectionIndex, docIndex) {
    refreshCisHelpDataFromForm();
    cisHelpCardData.content.sections[sectionIndex].documents.splice(docIndex, 1);
    renderCisDocumentsEditor();
}

async function uploadCisDocumentImage(input) {
    const file = input.files?.[0];
    if (!file) return;

    const row = input.closest('.cis-document-edit');
    const formData = new FormData();
    formData.append('image', file);
    input.disabled = true;

    try {
        const response = await fetch('/api/admin/objects/help-cards/cis-documents/images', {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Ошибка загрузки');
        }

        row.querySelector('.cis-document-image-url').value = result.url;
        showNotification('✅ Картинка загружена', 'success');
        refreshCisHelpDataFromForm();
        renderCisDocumentsEditor();
    } catch (error) {
        console.error('Ошибка загрузки картинки:', error);
        showNotification('❌ ' + error.message, 'error');
    } finally {
        input.disabled = false;
    }
}

async function saveCisDocumentsHelpCard() {
    const payload = collectCisDocumentsEditorData();

    try {
        const response = await fetch('/api/admin/objects/help-cards/cis-documents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || 'Ошибка сохранения');
        }

        cisHelpCardData = payload;
        showNotification('✅ Шпаргалка сохранена', 'success');
        closeCisDocumentsEditor();
    } catch (error) {
        console.error('Ошибка сохранения шпаргалки:', error);
        showNotification('❌ ' + error.message, 'error');
    }
}

// Следим за изменением размера окна
let resizeTimerObjects;
window.addEventListener('resize', function() {
    clearTimeout(resizeTimerObjects);
    resizeTimerObjects = setTimeout(function() {
        if (objectsList.length > 0) {
            renderObjectsTable(objectsList);
        }
    }, 250);
});

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    // Проверяем, что мы на странице с управлением объектами
    if (document.getElementById('objectsTableContainer')) {
        loadObjects();
    }
});

// Делаем функции глобальными
window.openAddObjectModal = openAddObjectModal;
window.editObject = editObject;
window.editObjectPassport = editObjectPassport;
window.deleteObject = deleteObject;
window.saveObject = saveObject;
window.closeObjectModal = closeObjectModal;
window.filterObjects = filterObjects;
window.loadObjects = loadObjects;
