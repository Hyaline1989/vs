// static/selection.js - полная версия с разделением по гражданству (РФ/СНГ), без кнопок показать/скрыть все

// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
let objects = [];
let vacancyData = {};
let globalOrder = [];
let debugMode = false;
let hasUnsavedChanges = false;
let currentUserRole = null;

// ========== ФУНКЦИИ ДЛЯ ПОДБОРА ОБЪЕКТОВ ==========
async function loadSelectionData() {
    try {
        console.log('Загрузка данных для подбора объектов...');
        
        // Получаем текущего пользователя
        const userResponse = await fetch('/api/auth/me', { credentials: 'include' });
        if (userResponse.ok) {
            const userData = await userResponse.json();
            currentUserRole = userData.role;
            window.currentUserRole = userData.role;
            window.isAdmin = (userData.role === 'admin' || userData.is_system_admin);
            console.log('Роль пользователя:', currentUserRole, 'isAdmin:', window.isAdmin);
        }
        
        // Очищаем старые данные
        const resultsContainer = document.getElementById('results');
        if (resultsContainer) {
            resultsContainer.innerHTML = '<div class="loading">Загрузка объектов...</div>';
        }
        
        const response = await fetch('/api/selection/settings', { credentials: 'include' });
        const data = await response.json();
        
        if (data.error) {
            console.error('Ошибка:', data.error);
            showNotification('Ошибка загрузки данных: ' + escapeHtml(data.error), 'error');
            return;
        }
        
        objects = data.objects || [];
        globalOrder = data.globalOrder || [];
        vacancyData = data.vacancyData || {};
        
        console.log('Загружено объектов:', objects.length);
        console.log('Приоритетных объектов:', objects.filter(o => o.priority).length);
        
        // Показываем админ-контролы если пользователь админ
        if (window.isAdmin) {
            const adminControls = document.getElementById('adminControls');
            if (adminControls) {
                adminControls.style.display = 'block';
                console.log('Админ-контролы показаны');
            }
        }
        
        filterAndDisplayObjects();
        initDragAndDrop();
        
        if (debugMode) updateDebugInfo();
    } catch (error) {
        console.error('Ошибка загрузки данных подбора:', error);
        showNotification('Ошибка загрузки данных', 'error');
    }
}

function filterAndDisplayObjects() {
    const age = parseInt(document.getElementById('age')?.value || 25);
    const gender = document.getElementById('gender')?.value || 'все';
    const nationality = document.getElementById('nationality')?.value || 'РФ';
    const hasConviction = document.getElementById('hasConviction')?.value === 'true';
    
    console.log('Фильтрация:', { age, gender, nationality, hasConviction });
    
    const filtered = objects.filter(obj => {
        if (!obj.visible) return false;
        
        // Проверка возраста
        const ageMatch = age >= obj.ageMin && age <= obj.ageMax;
        if (!ageMatch) return false;
        
        // Проверка гражданства
        let nationalityMatch = false;
        if (nationality === 'РФ') {
            nationalityMatch = obj.allowedNationalities && obj.allowedNationalities.includes('РФ');
        } else if (nationality === 'СНГ') {
            nationalityMatch = obj.allowedNationalities && obj.allowedNationalities.includes('СНГ');
        } else if (nationality === 'РБ') {
            nationalityMatch = obj.allowedNationalities && obj.allowedNationalities.includes('РБ');
        } else {
            nationalityMatch = true;
        }
        if (!nationalityMatch) return false;
        
        // Проверка судимости
        const convictionMatch = hasConviction ? obj.allowsConviction : true;
        if (!convictionMatch) return false;
        
        // Проверка вакансий по полу
        const stats = getVacancyStats(obj.name);
        const totalMen = stats.rf.men + stats.cis.men;
        const totalWomen = stats.rf.women + stats.cis.women;
        const totalFamily = stats.rf.family + stats.cis.family;
        
        if (gender === 'все') {
            return (totalMen > 0 || totalWomen > 0 || totalFamily > 0);
        } else if (gender === 'мужчина') {
            return obj.allowedGenders && obj.allowedGenders.includes('мужчина') && totalMen > 0;
        } else if (gender === 'женщина') {
            return obj.allowedGenders && obj.allowedGenders.includes('женщина') && totalWomen > 0;
        } else if (gender === 'семейные') {
            return totalFamily > 0;
        }
        return true;
    });
    
    console.log('Отфильтровано объектов:', filtered.length);
    displayResults(filtered);
}

function getVacancyStats(objectName) {
    if (!vacancyData || !vacancyData[objectName]) {
        return { 
            rf: { men: 0, women: 0, family: 0 },
            cis: { men: 0, women: 0, family: 0 },
            positions: [] 
        };
    }
    const data = vacancyData[objectName];
    return {
        rf: data.rf || { men: 0, women: 0, family: 0 },
        cis: data.cis || { men: 0, women: 0, family: 0 },
        positions: data.positions || []
    };
}

function displayResults(objectsToDisplay) {
    const container = document.getElementById('results');
    const countDisplay = document.getElementById('resultsCount');
    
    if (!container) return;
    
    // Сортировка: сначала приоритетные, потом по глобальному порядку
    const sorted = [...objectsToDisplay].sort((a, b) => {
        if (a.priority && !b.priority) return -1;
        if (!a.priority && b.priority) return 1;
        const idxA = globalOrder.indexOf(a.id);
        const idxB = globalOrder.indexOf(b.id);
        if (idxA === -1) return 1;
        if (idxB === -1) return -1;
        return idxA - idxB;
    });
    
    const priorityCount = sorted.filter(obj => obj.priority).length;
    if (countDisplay) {
        countDisplay.textContent = `Найдено объектов: ${sorted.length} (${priorityCount} в приоритете)`;
    }
    
    container.innerHTML = '';
    
    if (sorted.length === 0) {
        container.innerHTML = '<div class="no-results">По заданным критериям объектов не найдено</div>';
        return;
    }
    
    const isAdmin = window.isAdmin;
    
    sorted.forEach((obj, idx) => {
        const stats = getVacancyStats(obj.name);
        const isPriority = obj.priority;
        
        // Общие итоги (РФ + СНГ) для лицевой стороны
        const totalMen = stats.rf.men + stats.cis.men;
        const totalWomen = stats.rf.women + stats.cis.women;
        const totalFamily = stats.rf.family + stats.cis.family;
        
        const card = document.createElement('div');
        card.className = `flip-card ${isPriority ? 'priority-card' : ''}`;
        card.setAttribute('data-id', obj.id);
        
        const orderNumber = isAdmin ? `<span class="order-badge">${idx + 1}</span>` : '';
        const dragHandle = isAdmin ? '<div class="drag-handle-main">⋮⋮</div>' : '';
        
        const safeLink = escapeUrl(obj.link);
        
        // Формируем отображение гражданства
        let nationalityText = '';
        if (obj.allowedNationalities && obj.allowedNationalities.length > 0) {
            if (obj.allowedNationalities.includes('РФ') && obj.allowedNationalities.includes('СНГ')) {
                nationalityText = 'РФ + СНГ';
            } else if (obj.allowedNationalities.includes('РФ') && obj.allowedNationalities.includes('РБ')) {
                nationalityText = 'РФ + РБ';
            } else {
                nationalityText = obj.allowedNationalities.join(', ');
            }
        } else {
            nationalityText = 'Не указано';
        }
        
        card.innerHTML = `
            <div class="flip-card-inner">
                <div class="flip-card-front">
                    ${dragHandle}
                    <h3>${orderNumber}<a href="${safeLink}" target="_blank" rel="noopener noreferrer">${escapeHtml(obj.name)}</a>${isPriority ? ' 🔴' : ''}</h3>
                    <div class="vacancy-stats">
                        <div class="vacancy-stat">
                            <div class="vacancy-value vacancy-men">${totalMen}</div>
                            <div class="vacancy-label">Мужчины</div>
                        </div>
                        <div class="vacancy-stat">
                            <div class="vacancy-value vacancy-women">${totalWomen}</div>
                            <div class="vacancy-label">Женщины</div>
                        </div>
                        <div class="vacancy-stat">
                            <div class="vacancy-value vacancy-family">${totalFamily}</div>
                            <div class="vacancy-label">Семьи</div>
                        </div>
                    </div>
                    <p><strong>Возраст:</strong> ${escapeHtml(String(obj.ageMin))} - ${escapeHtml(String(obj.ageMax))} лет</p>
                    <p><strong>Гражданство:</strong> ${escapeHtml(nationalityText)}</p>
                    <p><strong>Судимость:</strong> ${obj.allowsConviction ? 'Принимают' : 'Не принимают'}</p>
                    <button class="flip-btn" onclick="flipCard(this)">Подробнее о должностях</button>
                </div>
                <div class="flip-card-back">
                    <h3>${orderNumber}${escapeHtml(obj.name)} - Должности</h3>
                    <div class="citizenship-tabs">
                        <div class="tab-buttons">
                            <button class="tab-btn active" data-tab="rf" onclick="showTab(this, 'rf')">РФ</button>
                            <button class="tab-btn" data-tab="cis" onclick="showTab(this, 'cis')">СНГ</button>
                        </div>
                        <div id="tab-rf" class="tab-content active">
                            <div class="positions-list">
                                ${stats.positions && stats.positions.length > 0 ? 
                                    stats.positions.map(p => `
                                        <div class="position-item">
                                            <div class="position-name">${escapeHtml(p.name)}</div>
                                            <div class="position-stats">
                                                ${p.rf.men > 0 ? `<span>Мужчины: ${p.rf.men}</span>` : ''}
                                                ${p.rf.women > 0 ? `<span>Женщины: ${p.rf.women}</span>` : ''}
                                                ${p.rf.family > 0 ? `<span>Семьи: ${p.rf.family}</span>` : ''}
                                            </div>
                                        </div>
                                    `).join('') : 
                                    '<div class="no-positions">Нет данных по должностям для РФ</div>'
                                }
                            </div>
                        </div>
                        <div id="tab-cis" class="tab-content">
                            <div class="positions-list">
                                ${stats.positions && stats.positions.length > 0 ? 
                                    stats.positions.map(p => `
                                        <div class="position-item">
                                            <div class="position-name">${escapeHtml(p.name)}</div>
                                            <div class="position-stats">
                                                ${p.cis.men > 0 ? `<span>Мужчины: ${p.cis.men}</span>` : ''}
                                                ${p.cis.women > 0 ? `<span>Женщины: ${p.cis.women}</span>` : ''}
                                                ${p.cis.family > 0 ? `<span>Семьи: ${p.cis.family}</span>` : ''}
                                            </div>
                                        </div>
                                    `).join('') : 
                                    '<div class="no-positions">Нет данных по должностям для СНГ</div>'
                                }
                            </div>
                        </div>
                    </div>
                    <button class="flip-btn" onclick="flipCard(this)">Назад</button>
                </div>
            </div>
        `;
        
        container.appendChild(card);
    });
}

// Функция для переключения вкладок (РФ/СНГ)
function showTab(btn, tabName) {
    // Находим родительский контейнер вкладок
    const tabsContainer = btn.closest('.citizenship-tabs');
    if (!tabsContainer) return;
    
    // Переключаем активный класс у кнопок
    const allBtns = tabsContainer.querySelectorAll('.tab-btn');
    allBtns.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    
    // Переключаем видимость контента
    const rfTab = tabsContainer.querySelector('#tab-rf');
    const cisTab = tabsContainer.querySelector('#tab-cis');
    
    if (tabName === 'rf') {
        if (rfTab) rfTab.classList.add('active');
        if (cisTab) cisTab.classList.remove('active');
    } else {
        if (rfTab) rfTab.classList.remove('active');
        if (cisTab) cisTab.classList.add('active');
    }
}

function flipCard(button) {
    const card = button.closest('.flip-card');
    if (card) card.classList.toggle('flipped');
}

function initDragAndDrop() {
    if (!window.isAdmin) {
        console.log('Drag and drop disabled - not admin');
        return;
    }
    
    const resultsContainer = document.getElementById('results');
    if (resultsContainer && typeof Sortable !== 'undefined') {
        console.log('Инициализация drag and drop для админа');
        new Sortable(resultsContainer, {
            handle: '.drag-handle-main',
            animation: 150,
            ghostClass: 'sortable-ghost',
            onEnd: updateGlobalOrderFromCards
        });
    }
}

function updateGlobalOrderFromCards() {
    const container = document.getElementById('results');
    const visibleIds = Array.from(container.children).map(card => parseInt(card.dataset.id));
    const hiddenIds = globalOrder.filter(id => !visibleIds.includes(id));
    globalOrder = [...visibleIds, ...hiddenIds];
    hasUnsavedChanges = true;
    updateSaveButtonState();
}

function updateSaveButtonState() {
    const saveBtn = document.getElementById('saveOrderBtn');
    if (saveBtn) {
        if (hasUnsavedChanges) {
            saveBtn.innerHTML = 'Сохранить порядок *';
            saveBtn.style.background = '#e74c3c';
        } else {
            saveBtn.innerHTML = 'Сохранить порядок';
            saveBtn.style.background = '#27ae60';
        }
    }
}

async function saveGlobalOrder() {
    if (!window.isAdmin) {
        showNotification('Только администратор может менять порядок', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/selection/order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ order: globalOrder })
        });
        
        if (response.ok) {
            hasUnsavedChanges = false;
            updateSaveButtonState();
            showNotification('Порядок сохранён', 'success');
        } else {
            showNotification('Ошибка сохранения порядка', 'error');
        }
    } catch (error) {
        console.error('Ошибка сохранения порядка:', error);
        showNotification('Не удалось сохранить порядок', 'error');
    }
}

function resetGlobalOrder() {
    if (!window.isAdmin) {
        showNotification('Только администратор может сбрасывать порядок', 'error');
        return;
    }
    
    if (confirm('Сбросить порядок объектов к исходному?')) {
        globalOrder = objects.map(obj => obj.id);
        hasUnsavedChanges = true;
        updateSaveButtonState();
        filterAndDisplayObjects();
        showNotification('Порядок сброшен, нажмите "Сохранить порядок"', 'info');
    }
}

function toggleDebug() {
    debugMode = !debugMode;
    const debugInfo = document.getElementById('debugInfo');
    if (debugInfo) {
        debugInfo.style.display = debugMode ? 'block' : 'none';
        if (debugMode) updateDebugInfo();
    }
}

function updateDebugInfo() {
    const debugInfo = document.getElementById('debugInfo');
    if (!debugInfo) return;
    
    let html = '<strong>Отладочная информация:</strong><br>';
    html += `- Роль пользователя: ${currentUserRole}<br>`;
    html += `- isAdmin: ${window.isAdmin}<br>`;
    html += `- Объектов в БД: ${escapeHtml(String(objects.length))}<br>`;
    html += `- Видимых объектов: ${escapeHtml(String(objects.filter(o => o.visible).length))}<br>`;
    html += `- Приоритетных объектов: ${escapeHtml(String(objects.filter(o => o.priority).length))}<br>`;
    html += `- Данных о вакансиях: ${escapeHtml(String(Object.keys(vacancyData).length))}<br>`;
    html += `- Время: ${escapeHtml(new Date().toLocaleString())}<br>`;
    debugInfo.innerHTML = html;
}

function fillMenuWithObjects() {
    const menuItems = document.getElementById('menuItems');
    if (!menuItems) return;
    
    menuItems.innerHTML = '';
    
    const sortedObjects = [...objects].sort((a, b) => {
        const idxA = globalOrder.indexOf(a.id);
        const idxB = globalOrder.indexOf(b.id);
        if (idxA === -1) return 1;
        if (idxB === -1) return -1;
        return idxA - idxB;
    });
    
    const isAdmin = window.isAdmin;
    
    sortedObjects.forEach((obj, index) => {
        const menuItem = document.createElement('div');
        menuItem.className = 'menu-item';
        menuItem.setAttribute('data-id', obj.id);
        
        let nationalityText = '';
        if (obj.allowedNationalities && obj.allowedNationalities.length > 0) {
            if (obj.allowedNationalities.includes('РФ') && obj.allowedNationalities.includes('СНГ')) {
                nationalityText = 'РФ + СНГ';
            } else if (obj.allowedNationalities.includes('РФ') && obj.allowedNationalities.includes('РБ')) {
                nationalityText = 'РФ + РБ';
            } else {
                nationalityText = obj.allowedNationalities.join(', ');
            }
        }
        
        menuItem.innerHTML = `
            <div class="menu-checkbox">
                ${isAdmin ? '<span class="drag-handle">⋮⋮</span>' : ''}
                <span class="order-number">${index + 1}</span>
                <input type="checkbox" ${obj.visible ? 'checked' : ''} 
                       onchange="handleCheckboxChange(${obj.id}, this.checked)">
                <span class="checkmark"></span>
                <div class="menu-object-info">
                    <strong>${escapeHtml(obj.name)}${obj.priority ? ' 🔴' : ''}</strong>
                    <div class="menu-details">
                        <span>${escapeHtml(String(obj.ageMin))}-${escapeHtml(String(obj.ageMax))} лет</span>
                        <span>${escapeHtml(obj.allowedGenders.join(', '))}</span>
                        <span>${escapeHtml(nationalityText)}</span>
                        <span>Судимость: ${obj.allowsConviction ? 'Да' : 'Нет'}</span>
                    </div>
                    ${isAdmin ? `
                        <button class="priority-toggle ${obj.priority ? 'priority-active' : ''}" 
                                onclick="togglePriority(${obj.id})">
                            ${obj.priority ? 'В приоритете' : 'Обычный'}
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
        menuItems.appendChild(menuItem);
    });
    
    if (isAdmin && typeof Sortable !== 'undefined') {
        const menuItemsContainer = document.getElementById('menuItems');
        if (menuItemsContainer && !menuItemsContainer.sortable) {
            new Sortable(menuItemsContainer, {
                handle: '.drag-handle',
                animation: 150,
                ghostClass: 'sortable-ghost',
                onEnd: function() {
                    const newOrder = Array.from(menuItemsContainer.children).map(item => 
                        parseInt(item.getAttribute('data-id'))
                    );
                    globalOrder = newOrder;
                    hasUnsavedChanges = true;
                    updateSaveButtonState();
                    filterAndDisplayObjects();
                }
            });
        }
    }
}

async function togglePriority(objectId) {
    if (!window.isAdmin) {
        showNotification('Только администратор может менять приоритеты', 'error');
        return;
    }
    
    const object = objects.find(obj => obj.id === objectId);
    if (!object) return;
    
    const newPriority = !object.priority;
    object.priority = newPriority;
    
    try {
        const response = await fetch(`/api/selection/object/${objectId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ 
                visible: object.visible, 
                priority: newPriority 
            })
        });
        
        if (response.ok) {
            showNotification(`${newPriority ? 'В приоритете' : 'Обычный'} - ${escapeHtml(object.name)}`, 'success');
            fillMenuWithObjects();
            filterAndDisplayObjects();
        } else {
            object.priority = !newPriority;
            showNotification('Ошибка сохранения приоритета', 'error');
        }
    } catch (error) {
        object.priority = !newPriority;
        console.error('Ошибка:', error);
        showNotification('Ошибка сохранения приоритета', 'error');
    }
}

async function handleCheckboxChange(objectId, isVisible) {
    if (!window.isAdmin) {
        showNotification('Только администратор может изменять видимость', 'error');
        return;
    }
    
    const object = objects.find(obj => obj.id === objectId);
    if (object) {
        object.visible = isVisible;
        
        try {
            const response = await fetch(`/api/selection/object/${objectId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ 
                    visible: isVisible, 
                    priority: object.priority 
                })
            });
            
            if (response.ok) {
                filterAndDisplayObjects();
            } else {
                object.visible = !isVisible;
                showNotification('Ошибка сохранения видимости', 'error');
            }
        } catch (error) {
            object.visible = !isVisible;
            console.error('Ошибка:', error);
            showNotification('Ошибка сохранения видимости', 'error');
        }
    }
}

// Глобальные функции для HTML
window.flipCard = flipCard;
window.showTab = showTab;
window.toggleDebug = toggleDebug;
window.saveGlobalOrder = saveGlobalOrder;
window.resetGlobalOrder = resetGlobalOrder;
window.togglePriority = togglePriority;
window.handleCheckboxChange = handleCheckboxChange;
window.loadSelectionData = loadSelectionData;
window.filterAndDisplayObjects = filterAndDisplayObjects;