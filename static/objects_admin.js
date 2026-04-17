// static/objects_admin.js
// Управление объектами в админ-панели
// static/objects_admin.js - добавьте в самое начало

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
                        ${obj.link ? `<div><i class="fas fa-link"></i> <a href="${escapeHtml(obj.link)}" target="_blank">Ссылка</a></div>` : ''}
                    </div>
                    <div class="object-card-actions">
                        <button class="action-btn edit-btn" onclick="editObject(${obj.id})" title="Редактировать">
                            <i class="fas fa-edit"></i> Редактировать
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
    
    // Таблица для десктопа - убран столбец "Приоритет"
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
                <td><strong>${escapeHtml(obj.name)}</strong>${obj.link ? `<br><a href="${escapeHtml(obj.link)}" target="_blank" class="object-link"><i class="fas fa-external-link-alt"></i></a>` : ''}</td>
                <td>${obj.ageMin} - ${obj.ageMax}</td>
                <td>${obj.allowedGenders?.join(', ') || '-'}</td>
                <td>${obj.allowedNationalities?.join(', ') || '-'}</td>
                <td>${obj.allowsConviction ? '<span class="allowed">Разрешена</span>' : '<span class="forbidden">Запрещена</span>'}</td>
                <td><span class="visibility-badge ${visibleClass}"><i class="fas ${visibleIcon}"></i> ${obj.visible ? 'Видим' : 'Скрыт'}</span></td>
                <td class="actions-cell">
                    <button class="action-btn edit-btn" onclick="editObject(${obj.id})" title="Редактировать"><i class="fas fa-edit"></i></button>
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
    
    // Устанавливаем значения по умолчанию
    document.getElementById('objAgeMin').value = '18';
    document.getElementById('objAgeMax').value = '55';
    document.getElementById('objAllowedGenders').value = 'мужчина,женщина';
    document.getElementById('objAllowedNationalities').value = 'РФ';
    document.getElementById('objAllowsConviction').checked = false;
    document.getElementById('objVisible').checked = true;
    
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
    document.getElementById('objAgeMin').value = obj.ageMin || 18;
    document.getElementById('objAgeMax').value = obj.ageMax || 55;
    document.getElementById('objAllowedGenders').value = (obj.allowedGenders || []).join(',');
    document.getElementById('objAllowedNationalities').value = (obj.allowedNationalities || []).join(',');
    document.getElementById('objAllowsConviction').checked = obj.allowsConviction || false;
    document.getElementById('objLink').value = obj.link || '';
    document.getElementById('objVisible').checked = obj.visible !== false;
    
    document.getElementById('objectModal').style.display = 'flex';
}

// ========== СОХРАНЕНИЕ ОБЪЕКТА ==========
async function saveObject() {
    const objectId = document.getElementById('objectId').value;
    const name = document.getElementById('objName').value.trim();
    const ageMin = parseInt(document.getElementById('objAgeMin').value);
    const ageMax = parseInt(document.getElementById('objAgeMax').value);
    const allowedGendersStr = document.getElementById('objAllowedGenders').value;
    const allowedNationalitiesStr = document.getElementById('objAllowedNationalities').value;
    const allowsConviction = document.getElementById('objAllowsConviction').checked;
    const link = document.getElementById('objLink').value.trim();
    const visible = document.getElementById('objVisible').checked;
    
    // Валидация
    if (!name) {
        showNotification('❌ Введите название объекта', 'error');
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
    
    const allowedGenders = allowedGendersStr.split(',').map(g => g.trim()).filter(g => g);
    if (allowedGenders.length === 0) {
        showNotification('❌ Укажите хотя бы один допустимый пол', 'error');
        return;
    }
    
    const allowedNationalities = allowedNationalitiesStr.split(',').map(n => n.trim()).filter(n => n);
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
        link,
        visible
    };
    
    try {
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
            const error = await response.json();
            showNotification('❌ ' + (error.error || 'Ошибка сохранения'), 'error');
        }
    } catch (error) {
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

// ========== ФИЛЬТРАЦИЯ ОБЪЕКТОВ (убрана фильтрация по приоритету) ==========
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
            const visibilityCell = row.cells[6]?.textContent.toLowerCase() || '';
            
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
window.deleteObject = deleteObject;
window.saveObject = saveObject;
window.closeObjectModal = closeObjectModal;
window.filterObjects = filterObjects;
window.loadObjects = loadObjects;