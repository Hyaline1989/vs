// static/selection.js - ПОЛНАЯ ВЕРСИЯ С АВТОЗАПОЛНЕНИЕМ ИЗ ПРОФИЛЯ (ОБНОВЛЕНА: раздельные Имя/Фамилия/Отчество)
// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
let objects = [];
let vacancyData = {};
let globalOrder = [];
let debugMode = false;
let hasUnsavedChanges = false;
let currentUserRole = null;
let currentUserProfile = null;  // Данные профиля текущего пользователя

// ========== СИСТЕМА УВЕДОМЛЕНИЙ ==========
function showToast(message, type = 'info') {
    const oldToast = document.getElementById('selectionToast');
    if (oldToast) oldToast.remove();
    
    const toast = document.createElement('div');
    toast.id = 'selectionToast';
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 24px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        animation: slideIn 0.3s ease;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;
    
    const colors = { success: '#27ae60', error: '#e74c3c', info: '#3498db', warning: '#f39c12' };
    toast.style.background = colors[type] || colors.info;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.animation = 'slideOut 0.3s ease'; setTimeout(() => toast.remove(), 300); }, 3000);
}

// ========== ЗАГРУЗКА ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ ==========
async function loadCurrentUserProfile() {
    try {
        const response = await fetch('/api/profile', { credentials: 'include' });
        if (response.ok) {
            currentUserProfile = await response.json();
            console.log('✅ Профиль загружен:', currentUserProfile);
        } else {
            console.warn('Не удалось загрузить профиль пользователя');
        }
    } catch (error) {
        console.error('Ошибка загрузки профиля:', error);
    }
}

// ========== ЗАГРУЗКА ДАННЫХ ==========
async function loadSelectionData() {
    try {
        console.log('Загрузка данных для подбора объектов...');
        
        // Загружаем профиль пользователя
        if (!currentUserProfile) {
            await loadCurrentUserProfile();
        }
        
        const userResponse = await fetch('/api/auth/me', { credentials: 'include' });
        if (userResponse.ok) {
            const userData = await userResponse.json();
            currentUserRole = userData.role;
            window.currentUserRole = userData.role;
            window.isAdmin = (userData.role === 'admin' || userData.is_system_admin);
        }
        
        const resultsContainer = document.getElementById('results');
        if (resultsContainer) resultsContainer.innerHTML = '<div class="loading">Загрузка объектов...</div>';
        
        const response = await fetch(`/api/selection/settings`, { credentials: 'include' });
        const data = await response.json();
        
        if (data.error) { showToast('Ошибка загрузки данных: ' + escapeHtml(data.error), 'error'); return; }
        
        objects = data.objects || [];
        globalOrder = data.globalOrder || [];
        
        await loadVacancyData();
        
        // Синхронизируем приоритеты из vacancyData в objects
        for (const obj of objects) {
            if (vacancyData[obj.name] && vacancyData[obj.name].is_high === true) {
                obj.priority = true;
                console.log(`✅ Установлен приоритет для ${obj.name} из vacancyData`);
            }
        }
        
        // Только админ видит блок управления объектами
        if (window.isAdmin) {
            const adminControls = document.getElementById('adminControls');
            if (adminControls) adminControls.style.display = 'block';
        }
        
        filterAndDisplayObjects();
        initDragAndDrop();
        if (debugMode) updateDebugInfo();
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        showToast('Ошибка загрузки данных', 'error');
    }
}

async function loadVacancyData() {
    try {
        const response = await fetch(`/api/requirements/vacancy`, { 
            credentials: 'include' 
        });
        const data = await response.json();
        
        if (!data.error) {
            vacancyData = data.data || {};
            
            // Синхронизируем приоритеты из vacancyData с objects
            for (const objName in vacancyData) {
                const obj = objects.find(o => o.name === objName);
                if (obj && vacancyData[objName]) {
                    obj.priority = vacancyData[objName].is_high || false;
                }
            }
            
            console.log(`📊 Загружены текущие потребности: ${Object.keys(vacancyData).length} объектов`);
        }
    } catch (error) {
        console.error('Ошибка загрузки потребностей:', error);
    }
}

// ========== ФИЛЬТРАЦИЯ ОБЪЕКТОВ ==========
function filterAndDisplayObjects() {
    const age = parseInt(document.getElementById('age')?.value || 25);
    const gender = document.getElementById('gender')?.value || 'все';
    const nationality = document.getElementById('nationality')?.value || 'все';
    const hasConviction = document.getElementById('hasConviction')?.value === 'true';
    
    const filtered = objects.filter(obj => {
        if (!obj.visible) return false;
        
        const ageMatch = age >= obj.ageMin && age <= obj.ageMax;
        if (!ageMatch) return false;
        
        const convictionMatch = hasConviction ? obj.allowsConviction : true;
        if (!convictionMatch) return false;
        
        const stats = getVacancyStats(obj.name);
        
        const totalMen = (stats.rf?.men || 0) + (stats.cis?.men || 0);
        const totalWomen = (stats.rf?.women || 0) + (stats.cis?.women || 0);
        const totalFamily = (stats.rf?.family || 0) + (stats.cis?.family || 0);
        const totalAll = totalMen + totalWomen + totalFamily;
        
        if (totalAll === 0) return false;
        
        let nationalityMatch = false;
        
        switch (nationality) {
            case 'РФ':
                const needRFMen = (stats.rf?.men || 0) > 0;
                const needRFWomen = (stats.rf?.women || 0) > 0;
                const needRFFamily = (stats.rf?.family || 0) > 0;
                nationalityMatch = needRFMen || needRFWomen || needRFFamily;
                break;
                
            case 'СНГ':
                const needCISMen = (stats.cis?.men || 0) > 0;
                const needCISWomen = (stats.cis?.women || 0) > 0;
                const needCISFamily = (stats.cis?.family || 0) > 0;
                nationalityMatch = needCISMen || needCISWomen || needCISFamily;
                break;
                
            case 'все':
                nationalityMatch = true;
                break;
                
            default:
                nationalityMatch = true;
        }
        
        if (!nationalityMatch) return false;
        
        if (gender === 'мужчина') {
            const needMen = (stats.rf?.men || 0) > 0 || (stats.cis?.men || 0) > 0;
            if (!needMen) return false;
            if (!obj.allowedGenders?.includes('мужчина')) return false;
        }
        else if (gender === 'женщина') {
            const needWomen = (stats.rf?.women || 0) > 0 || (stats.cis?.women || 0) > 0;
            if (!needWomen) return false;
            if (!obj.allowedGenders?.includes('женщина')) return false;
        }
        else if (gender === 'семейные') {
            const needFamily = (stats.rf?.family || 0) > 0 || (stats.cis?.family || 0) > 0;
            if (!needFamily) return false;
        }
        
        return true;
    });
    
    displayResults(filtered);
}

function getVacancyStats(objectName) {
    if (!vacancyData || !vacancyData[objectName]) {
        return { rf: { men: 0, women: 0, family: 0 }, cis: { men: 0, women: 0, family: 0 }, positions: [] };
    }
    return vacancyData[objectName];
}

// ========== ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ ==========
function displayResults(objectsToDisplay) {
    const container = document.getElementById('results');
    const countDisplay = document.getElementById('resultsCount');
    if (!container) return;
    
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
    if (countDisplay) countDisplay.textContent = `Найдено объектов: ${sorted.length} (${priorityCount} в приоритете)`;
    
    container.innerHTML = '';
    if (sorted.length === 0) {
        container.innerHTML = '<div class="no-results">По заданным критериям объектов не найдено</div>';
        return;
    }
    
    sorted.forEach((obj, idx) => {
        const stats = getVacancyStats(obj.name);
        
        const totalMen = (stats.rf?.men || 0) + (stats.cis?.men || 0);
        const totalWomen = (stats.rf?.women || 0) + (stats.cis?.women || 0);
        const totalFamily = (stats.rf?.family || 0) + (stats.cis?.family || 0);
        
        window.currentObjectName = obj.name;
        
        const card = document.createElement('div');
        card.className = `flip-card ${obj.priority ? 'priority-card' : ''}`;
        card.setAttribute('data-id', obj.id);
        
        const orderNumber = window.isAdmin ? `<span class="order-badge">${idx + 1}</span>` : '';
        const dragHandle = window.isAdmin ? '<div class="drag-handle-main">⋮⋮</div>' : '';
        
        let nationalityText = '';
        if (obj.allowedNationalities?.length > 0) {
            if (obj.allowedNationalities.includes('РФ') && obj.allowedNationalities.includes('СНГ')) nationalityText = 'РФ + СНГ';
            else if (obj.allowedNationalities.includes('РФ') && obj.allowedNationalities.includes('РБ')) nationalityText = 'РФ + РБ';
            else nationalityText = obj.allowedNationalities.join(', ');
        }
        
        card.innerHTML = `
            <div class="flip-card-inner">
                <div class="flip-card-front">
                    ${dragHandle}
                    <h3>${orderNumber}<a href="#" onclick="event.preventDefault(); viewPassport(${obj.id}, '${escapeHtml(obj.name)}')" style="cursor: pointer;">${escapeHtml(obj.name)}</a>${obj.priority ? ' 🔥' : ''}</h3>
                    <div class="vacancy-stats">
                        <div class="vacancy-stat"><div class="vacancy-value vacancy-men">${totalMen}</div><div class="vacancy-label">Мужчины</div></div>
                        <div class="vacancy-stat"><div class="vacancy-value vacancy-women">${totalWomen}</div><div class="vacancy-label">Женщины</div></div>
                        <div class="vacancy-stat"><div class="vacancy-value vacancy-family">${totalFamily}</div><div class="vacancy-label">Семьи</div></div>
                    </div>
                    <p><strong>Возраст:</strong> ${obj.ageMin} - ${obj.ageMax} лет</p>
                    <p><strong>Гражданство:</strong> ${nationalityText}</p>
                    <p><strong>Судимость:</strong> ${obj.allowsConviction ? 'Принимают' : 'Не принимают'}</p>
                    <div class="card-buttons">
                        <button class="direction-btn" onclick="openDirectionForm(${obj.id}, '${escapeHtml(obj.name)}', '')">
                            <i class="fas fa-paper-plane"></i> Направить сотрудника
                        </button>
                        <button class="flip-btn" onclick="flipCard(this)">Подробнее о должностях</button>
                    </div>
                </div>
                <div class="flip-card-back">
                    <h3>${orderNumber}${escapeHtml(obj.name)} - Должности</h3>
                    <div class="positions-list">
                        ${renderPositions(stats.positions, obj.id, obj.name)}
                    </div>
                    <button class="flip-btn" onclick="flipCard(this)">Назад</button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderPositions(positions, objectId, objectName) {
    if (!positions || positions.length === 0) {
        return '<div class="no-positions">Нет должностей</div>';
    }
    
    let html = '';
    
    for (const pos of positions) {
        const menRF = pos.rf?.men || 0;
        const womenRF = pos.rf?.women || 0;
        const familyRF = pos.rf?.family || 0;
        const menCIS = pos.cis?.men || 0;
        const womenCIS = pos.cis?.women || 0;
        const familyCIS = pos.cis?.family || 0;
        
        const total = menRF + womenRF + familyRF + menCIS + womenCIS + familyCIS;
        if (total === 0) continue;
        
        html += `
            <div class="position-item">
                <div class="position-name">${escapeHtml(pos.name)}</div>
                <div class="position-stats">
                    <span>🇷🇺 РФ: ${menRF}м ${womenRF}ж ${familyRF}с</span>
                    <span>🌍 СНГ: ${menCIS}м ${womenCIS}ж ${familyCIS}с</span>
                </div>
            </div>
        `;
    }
    
    if (html === '') {
        html = '<div class="no-positions">Нет должностей с потребностью</div>';
    }
    
    return html;
}

// ========== НАПРАВЛЕНИЕ СОТРУДНИКА (СОЗДАНИЕ ЛИДА) ==========

let currentDirectionObject = null;
let currentDirectionPosition = null;

async function openDirectionForm(objectId, objectName, positionName) {
    currentDirectionObject = { id: objectId, name: objectName };
    currentDirectionPosition = positionName || '';
    
    // Загружаем профиль пользователя, если ещё не загружен
    if (!currentUserProfile) {
        await loadCurrentUserProfile();
    }
    
    // Получаем данные для автозаполнения
    const agentName = currentUserProfile?.full_name || currentUserProfile?.username || '';
    const agentEmail = currentUserProfile?.email || '';
    
    let modal = document.getElementById('directionModal');
    if (modal) modal.remove();
    
    modal = document.createElement('div');
    modal.id = 'directionModal';
    modal.className = 'modal';
    modal.style.display = 'flex';
    
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 500px;">
            <div class="modal-header" style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);">
                <h3><i class="fas fa-paper-plane"></i> Направить сотрудника</h3>
                <button class="modal-close" onclick="closeDirectionModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="directionForm" onsubmit="submitDirection(event)">
                    <!-- 1. ИЗМЕНЕНО: три поля вместо одного -->
                    <div class="form-group">
                        <label>Фамилия кандидата *</label>
                        <input type="text" id="candidateLastName" required placeholder="Иванов" autocomplete="off">
                    </div>
                    <div class="form-group">
                        <label>Имя кандидата *</label>
                        <input type="text" id="candidateFirstName" required placeholder="Иван" autocomplete="off">
                    </div>
                    <div class="form-group">
                        <label>Отчество кандидата</label>
                        <input type="text" id="candidatePatronymic" placeholder="Иванович" autocomplete="off">
                    </div>
                    
                    <div class="form-group">
                        <label>Номер телефона *</label>
                        <input type="tel" id="candidatePhone" required placeholder="+7 (XXX) XXX-XX-XX" autocomplete="off">
                    </div>
                    
                    <div class="form-group">
                        <label>ФИО агента *</label>
                        <input type="text" id="agentName" required value="${escapeHtml(agentName)}" placeholder="Петров Петр Петрович" readonly style="background: #f5f5f5; cursor: default;">
                        <div class="info-text" style="font-size: 0.7rem; color: #27ae60; margin-top: 4px;">
                            <i class="fas fa-user-check"></i> Автоматически из вашего профиля
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Email агента</label>
                        <input type="email" id="agentEmail" value="${escapeHtml(agentEmail)}" placeholder="example@mail.ru" readonly style="background: #f5f5f5; cursor: default;">
                        <div class="info-text" style="font-size: 0.7rem; color: var(--gray);">
                            <i class="fas fa-envelope"></i> Для обратной связи (из профиля)
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Объект *</label>
                        <input type="text" id="agentObject" required placeholder="Название объекта" autocomplete="off">
                        <div class="info-text" style="font-size: 0.7rem; color: var(--gray);">
                            <i class="fas fa-building"></i> Укажите объект, куда направляется кандидат
                        </div>
                    </div>
                    
                    <!-- 2. ИЗМЕНЕНО: название блока файлов -->
                    <div class="form-group">
                        <label>Сканы документов</label>
                        <div id="fileList" class="file-list"></div>
                        <button type="button" class="btn-small" onclick="addFileInput()" style="margin-top: 8px; background: #3498db;">
                            <i class="fas fa-plus"></i> Добавить файл
                        </button>
                        <div class="info-text" style="margin-top: 8px;">
                            <i class="fas fa-info-circle"></i> 
                            Поддерживаются: PDF, DOC, DOCX, JPG, PNG. Максимум 10 файлов, каждый до 10 MB
                        </div>
                    </div>
                    
                    <div class="form-actions">
                        <button type="button" class="btn-cancel" onclick="closeDirectionModal()">Отмена</button>
                        <button type="submit" class="btn-save" style="background: #27ae60;">
                            <i class="fas fa-paper-plane"></i> Направить
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    addFileInput();
    
    // Автоматически фокусируемся на первом поле
    setTimeout(() => {
        const candidateLastNameInput = document.getElementById('candidateLastName');
        if (candidateLastNameInput) candidateLastNameInput.focus();
    }, 100);
}

function addFileInput() {
    const fileList = document.getElementById('fileList');
    if (!fileList) return;
    
    const fileCount = fileList.querySelectorAll('.file-input-wrapper').length;
    
    if (fileCount >= 10) {
        showToast('Максимум 10 файлов', 'warning');
        return;
    }
    
    const wrapper = document.createElement('div');
    wrapper.className = 'file-input-wrapper';
    wrapper.style.cssText = 'display: flex; gap: 8px; margin-bottom: 8px; align-items: center;';
    wrapper.innerHTML = `
        <input type="file" name="attachments" class="file-input" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" style="flex: 1; padding: 6px; border: 1px solid #ddd; border-radius: 6px;">
        <button type="button" class="remove-file-btn" onclick="this.parentElement.remove()" style="background: #e74c3c; color: white; border: none; width: 30px; height: 30px; border-radius: 4px; cursor: pointer; font-size: 14px;">✕</button>
    `;
    fileList.appendChild(wrapper);
}

function closeDirectionModal() {
    const modal = document.getElementById('directionModal');
    if (modal) modal.remove();
    currentDirectionObject = null;
    currentDirectionPosition = null;
}

// ОБНОВЛЕНО: отправка данных с раздельными полями
async function submitDirection(event) {
    event.preventDefault();
    
    const lastName = document.getElementById('candidateLastName')?.value.trim();
    const firstName = document.getElementById('candidateFirstName')?.value.trim();
    const patronymic = document.getElementById('candidatePatronymic')?.value.trim();
    const candidatePhone = document.getElementById('candidatePhone')?.value.trim();
    const agentName = document.getElementById('agentName')?.value.trim();
    const agentEmail = document.getElementById('agentEmail')?.value.trim();
    const agentObject = document.getElementById('agentObject')?.value.trim();
    
    // Валидация
    if (!lastName) {
        showToast('Введите фамилию кандидата', 'error');
        return;
    }
    if (!firstName) {
        showToast('Введите имя кандидата', 'error');
        return;
    }
    if (!candidatePhone) {
        showToast('Введите номер телефона', 'error');
        return;
    }
    if (!agentName) {
        showToast('Введите ФИО агента', 'error');
        return;
    }
    if (!agentObject) {
        showToast('Введите объект', 'error');
        return;
    }
    
    const phoneDigits = candidatePhone.replace(/\D/g, '');
    if (phoneDigits.length < 10) {
        showToast('Введите корректный номер телефона (минимум 10 цифр)', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('object_id', currentDirectionObject.id);
    formData.append('object_name', currentDirectionObject.name);
    formData.append('position_name', currentDirectionPosition || '');
    
    // Отправляем раздельно
    formData.append('candidate_last_name', lastName);
    formData.append('candidate_first_name', firstName);
    formData.append('candidate_patronymic', patronymic);
    formData.append('candidate_phone', candidatePhone);
    formData.append('agent_name', agentName);
    formData.append('agent_email', agentEmail);
    formData.append('agent_object', agentObject);
    
    const fileInputs = document.querySelectorAll('.file-input');
    fileInputs.forEach(input => {
        if (input.files && input.files[0]) {
            formData.append('attachments', input.files[0]);
        }
    });
    
    const submitBtn = document.querySelector('#directionForm .btn-save');
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
    
    try {
        const response = await fetch('/api/selection/create-deal', {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            showToast(`✅ Лид создан! ID: ${result.lead_id}`, 'success');
            closeDirectionModal();
            if (typeof loadSelectionData === 'function') {
                setTimeout(() => loadSelectionData(), 1000);
            }
        } else {
            showToast(`❌ Ошибка: ${result.error || 'Не удалось создать лид'}`, 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showToast('❌ Ошибка при отправке. Проверьте соединение.', 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

// ========== ГЛАВНОЕ МОДАЛЬНОЕ ОКНО ДЛЯ УПРАВЛЕНИЯ ПОТРЕБНОСТЯМИ ==========
async function openRequirementsModal() {
    if (!window.isAdmin) {
        showToast('Только администратор может управлять потребностями', 'error');
        return;
    }
    
    let modal = document.getElementById('requirementsModal');
    if (modal) modal.remove();
    
    showToast('Загрузка...', 'info');
    
    try {
        await loadVacancyData();
        renderRequirementsTable();
    } catch (error) {
        console.error('Ошибка:', error);
        showToast('Ошибка загрузки', 'error');
    }
}

function renderRequirementsTable() {
    const objectNames = Object.keys(vacancyData).sort();
    
    let tableHtml = `
        <div id="requirementsModal" class="requirements-modal">
            <div class="requirements-modal-content" style="max-width: 95%; width: 1400px;">
                <div class="requirements-modal-header">
                    <h3>📊 Управление потребностями в персонале</h3>
                    <div>
                        <button class="btn-add-object" onclick="showAddObjectModal()" style="background: #27ae60; color: white; border: none; padding: 6px 12px; border-radius: 4px; margin-right: 10px; cursor: pointer;">
                            + Добавить объект
                        </button>
                        <span class="requirements-modal-close" onclick="closeRequirementsModal()" style="cursor: pointer; font-size: 28px;">&times;</span>
                    </div>
                </div>
                <div class="requirements-modal-body">
                    <table class="requirements-table">
                        <thead>
                            <tr><th rowspan="2">Объект</th><th rowspan="2">Должность</th>
                                <th colspan="3">РФ / РБ</th><th colspan="3">СНГ</th>
                                <th rowspan="2">Всего</th><th rowspan="2">Приоритет</th>
                            </tr>
                            <tr><th>М</th><th>Ж</th><th>Семьи</th><th>М</th><th>Ж</th><th>Семьи</th></tr>
                        </thead>
                        <tbody>
    `;
    
    let grandTotal = 0;
    
    for (const objName of objectNames) {
        const objData = vacancyData[objName];
        const positions = objData?.positions || [];
        const rowCount = positions.length + 1;
        
        let totals = { rfMen: 0, rfWomen: 0, rfFamily: 0, cisMen: 0, cisWomen: 0, cisFamily: 0 };
        for (const pos of positions) {
            totals.rfMen += pos.rf?.men || 0;
            totals.rfWomen += pos.rf?.women || 0;
            totals.rfFamily += pos.rf?.family || 0;
            totals.cisMen += pos.cis?.men || 0;
            totals.cisWomen += pos.cis?.women || 0;
            totals.cisFamily += pos.cis?.family || 0;
        }
        const totalAll = totals.rfMen + totals.rfWomen + totals.rfFamily + totals.cisMen + totals.cisWomen + totals.cisFamily;
        grandTotal += totalAll;
        
        const isPriority = objData?.is_high || false;
        
        const safeObjNameForJs = objName.replace(/'/g, "\\'");
        
        for (let i = 0; i < positions.length; i++) {
            const pos = positions[i];
            const rowTotal = (pos.rf?.men||0) + (pos.rf?.women||0) + (pos.rf?.family||0) + 
                           (pos.cis?.men||0) + (pos.cis?.women||0) + (pos.cis?.family||0);
            
            const safePosName = pos.name.replace(/'/g, "\\'");
            
            tableHtml += `<tr data-obj="${escapeHtml(objName)}" data-pos="${escapeHtml(pos.name)}">
                ${i === 0 ? `<td rowspan="${rowCount}" style="vertical-align:middle; background:#f9f9f9;">
                    ${escapeHtml(objName)}
                    <button onclick="deleteObject('${safeObjNameForJs}')" style="display:block; margin-top:8px; background:#e74c3c; color:white; border:none; padding:3px 8px; border-radius:3px; font-size:11px; cursor:pointer;">🗑 Удалить объект</button>
                    <button onclick="showAddPositionModal('${safeObjNameForJs}')" style="display:block; margin-top:5px; background:#3498db; color:white; border:none; padding:3px 8px; border-radius:3px; font-size:11px; cursor:pointer;">+ Добавить должность</button>
                    </td>` : ''}
                <td>${escapeHtml(pos.name)} <button onclick="deletePosition('${safeObjNameForJs}','${safePosName}')" style="margin-left:8px; background:#e74c3c; color:white; border:none; padding:2px 6px; border-radius:3px; font-size:10px; cursor:pointer;">✕</button></td>
                <td><input type="number" class="editable rf-men" data-obj="${escapeHtml(objName)}" data-pos="${escapeHtml(pos.name)}" value="${pos.rf?.men||0}" min="0" style="width:60px; text-align:center;"></td>
                <td><input type="number" class="editable rf-women" data-obj="${escapeHtml(objName)}" data-pos="${escapeHtml(pos.name)}" value="${pos.rf?.women||0}" min="0" style="width:60px; text-align:center;"></td>
                <td><input type="number" class="editable rf-family" data-obj="${escapeHtml(objName)}" data-pos="${escapeHtml(pos.name)}" value="${pos.rf?.family||0}" min="0" style="width:60px; text-align:center;"></td>
                <td><input type="number" class="editable cis-men" data-obj="${escapeHtml(objName)}" data-pos="${escapeHtml(pos.name)}" value="${pos.cis?.men||0}" min="0" style="width:60px; text-align:center;"></td>
                <td><input type="number" class="editable cis-women" data-obj="${escapeHtml(objName)}" data-pos="${escapeHtml(pos.name)}" value="${pos.cis?.women||0}" min="0" style="width:60px; text-align:center;"></td>
                <td><input type="number" class="editable cis-family" data-obj="${escapeHtml(objName)}" data-pos="${escapeHtml(pos.name)}" value="${pos.cis?.family||0}" min="0" style="width:60px; text-align:center;"></td>
                <td class="row-total" style="background:#e8f4f8; font-weight:bold; text-align:center;">${rowTotal}</td>
                ${i === 0 ? `<td rowspan="${rowCount}" style="text-align:center; vertical-align:middle; background:#fff3cd;">
                    <input type="checkbox" class="priority-checkbox" data-obj="${escapeHtml(objName)}" ${isPriority ? 'checked' : ''} style="width:20px; height:20px;">
                    </td>` : ''}
              </tr>`;
        }
        
        tableHtml += `<tr style="background:#f0f0f0; font-weight:bold;">
            <td style="text-align:right;">📊 ВСЕГО:</td>
            <td><input type="text" value="${totals.rfMen}" readonly style="width:60px; text-align:center; background:#e8e8e8;"></td>
            <td><input type="text" value="${totals.rfWomen}" readonly style="width:60px; text-align:center; background:#e8e8e8;"></td>
            <td><input type="text" value="${totals.rfFamily}" readonly style="width:60px; text-align:center; background:#e8e8e8;"></td>
            <td><input type="text" value="${totals.cisMen}" readonly style="width:60px; text-align:center; background:#e8e8e8;"></td>
            <td><input type="text" value="${totals.cisWomen}" readonly style="width:60px; text-align:center; background:#e8e8e8;"></td>
            <td><input type="text" value="${totals.cisFamily}" readonly style="width:60px; text-align:center; background:#e8e8e8;"></td>
            <td style="background:#d4edda; text-align:center;">${totalAll}</td>
            <td style="background:#f0f0f0;"></td>
          </tr>`;
    }
    
    if (objectNames.length === 0) {
        tableHtml += `<tr><td colspan="10" style="text-align:center; padding:40px;">Нет объектов. Нажмите "Добавить объект"</td></tr>`;
    }
    
    tableHtml += `
                        </tbody>
                        <tfoot><tr style="background:#2c3e50; color:white;"><td colspan="8" style="text-align:right;"><strong>ОБЩИЙ ИТОГ:</strong></td><td style="text-align:center;"><strong>${grandTotal}</strong></td><td style="background:#2c3e50;"></td></tr></tfoot>
                    </table>
                </div>
                <div class="requirements-modal-footer">
                    <button onclick="closeRequirementsModal()" style="background:#6c757d; color:white; border:none; padding:8px 20px; border-radius:4px; margin-right:10px;">Отмена</button>
                    <button onclick="saveAllData()" style="background:#27ae60; color:white; border:none; padding:8px 20px; border-radius:4px;">💾 Сохранить всё</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(createElementFromHtml(tableHtml));
    
    document.querySelectorAll('.editable').forEach(field => {
        field.addEventListener('input', function() { 
            updateRowTotals(this.getAttribute('data-obj')); 
        });
    });
}

function updateRowTotals(objectName) {
    const rows = document.querySelectorAll(`tr[data-obj="${objectName}"]`);
    let totals = { rfMen:0, rfWomen:0, rfFamily:0, cisMen:0, cisWomen:0, cisFamily:0 };
    
    for (const row of rows) {
        const rfMen = parseInt(row.querySelector('.rf-men')?.value) || 0;
        const rfWomen = parseInt(row.querySelector('.rf-women')?.value) || 0;
        const rfFamily = parseInt(row.querySelector('.rf-family')?.value) || 0;
        const cisMen = parseInt(row.querySelector('.cis-men')?.value) || 0;
        const cisWomen = parseInt(row.querySelector('.cis-women')?.value) || 0;
        const cisFamily = parseInt(row.querySelector('.cis-family')?.value) || 0;
        
        totals.rfMen += rfMen;
        totals.rfWomen += rfWomen;
        totals.rfFamily += rfFamily;
        totals.cisMen += cisMen;
        totals.cisWomen += cisWomen;
        totals.cisFamily += cisFamily;
        
        const total = rfMen + rfWomen + rfFamily + cisMen + cisWomen + cisFamily;
        const totalCell = row.querySelector('.row-total');
        if (totalCell) totalCell.textContent = total;
    }
    
    const tbody = rows[0]?.closest('tbody');
    if (tbody) {
        const allRows = tbody.querySelectorAll('tr');
        for (const row of allRows) {
            const firstCell = row.cells[0];
            if (firstCell && firstCell.textContent.includes('ВСЕГО:')) {
                const cells = row.cells;
                if (cells[1]) { let input = cells[1].querySelector('input'); if (input) input.value = totals.rfMen; }
                if (cells[2]) { let input = cells[2].querySelector('input'); if (input) input.value = totals.rfWomen; }
                if (cells[3]) { let input = cells[3].querySelector('input'); if (input) input.value = totals.rfFamily; }
                if (cells[4]) { let input = cells[4].querySelector('input'); if (input) input.value = totals.cisMen; }
                if (cells[5]) { let input = cells[5].querySelector('input'); if (input) input.value = totals.cisWomen; }
                if (cells[6]) { let input = cells[6].querySelector('input'); if (input) input.value = totals.cisFamily; }
                const totalAll = totals.rfMen + totals.rfWomen + totals.rfFamily + totals.cisMen + totals.cisWomen + totals.cisFamily;
                if (cells[7]) cells[7].textContent = totalAll;
                break;
            }
        }
    }
    
    updateGrandTotal();
}

function updateGrandTotal() {
    let grandTotal = 0;
    const allTotalRows = document.querySelectorAll('tr');
    for (const row of allTotalRows) {
        const firstCell = row.cells[0];
        if (firstCell && firstCell.textContent.includes('ВСЕГО:')) {
            const lastCell = row.cells[row.cells.length - 1];
            if (lastCell) {
                const val = parseInt(lastCell.textContent) || 0;
                grandTotal += val;
            }
        }
    }
    const footerCell = document.querySelector('tfoot td:last-child');
    if (footerCell) footerCell.textContent = grandTotal;
}

// ========== СОХРАНЕНИЕ ВСЕХ ДАННЫХ ==========
async function saveAllData() {
    try {
        const objectsData = {};
        const editableFields = document.querySelectorAll('.editable');
        
        for (const field of editableFields) {
            const objName = field.getAttribute('data-obj');
            const posName = field.getAttribute('data-pos');
            
            if (!objectsData[objName]) {
                objectsData[objName] = { positions: [] };
            }
            
            let pos = objectsData[objName].positions.find(p => p.name === posName);
            if (!pos) {
                pos = { name: posName, rf: {}, cis: {} };
                objectsData[objName].positions.push(pos);
            }
            
            const className = field.className;
            const value = parseInt(field.value) || 0;
            
            if (className.includes('rf-men')) pos.rf.men = value;
            else if (className.includes('rf-women')) pos.rf.women = value;
            else if (className.includes('rf-family')) pos.rf.family = value;
            else if (className.includes('cis-men')) pos.cis.men = value;
            else if (className.includes('cis-women')) pos.cis.women = value;
            else if (className.includes('cis-family')) pos.cis.family = value;
        }
        
        const priorityChecks = document.querySelectorAll('.priority-checkbox');
        for (const chk of priorityChecks) {
            const objName = chk.getAttribute('data-obj');
            if (objectsData[objName]) {
                objectsData[objName].is_high = chk.checked;
            }
        }
        
        const response = await fetch('/api/requirements/save-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                objects: objectsData
            })
        });
        
        if (response.ok) {
            for (const chk of priorityChecks) {
                const objName = chk.getAttribute('data-obj');
                const obj = objects.find(o => o.name === objName);
                if (obj) obj.priority = chk.checked;
                if (vacancyData[objName]) vacancyData[objName].is_high = chk.checked;
            }
            
            showToast('✅ Все данные сохранены', 'success');
            filterAndDisplayObjects();
            setTimeout(() => closeRequirementsModal(), 500);
        } else {
            const err = await response.json();
            showToast('❌ Ошибка: ' + (err.error || 'Не удалось сохранить'), 'error');
        }
    } catch (error) {
        console.error('Ошибка сохранения:', error);
        showToast('❌ Ошибка сохранения', 'error');
    }
}

// ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
function flipCard(button) {
    button.closest('.flip-card')?.classList.toggle('flipped');
}

function initDragAndDrop() {
    if (!window.isAdmin) return;
    const container = document.getElementById('results');
    if (container && typeof Sortable !== 'undefined') {
        new Sortable(container, { handle: '.drag-handle-main', animation: 150, onEnd: updateGlobalOrderFromCards });
    }
}

function updateGlobalOrderFromCards() {
    const container = document.getElementById('results');
    const visibleIds = Array.from(container.children).map(card => parseInt(card.dataset.id));
    const hiddenIds = globalOrder.filter(id => !visibleIds.includes(id));
    globalOrder = [...visibleIds, ...hiddenIds];
    hasUnsavedChanges = true;
    const saveBtn = document.getElementById('saveOrderBtn');
    if (saveBtn) { saveBtn.innerHTML = 'Сохранить порядок *'; saveBtn.style.background = '#e74c3c'; }
}

async function saveGlobalOrder() {
    if (!window.isAdmin) return;
    try {
        const response = await fetch('/api/selection/order', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' }, 
            credentials: 'include',
            body: JSON.stringify({ order: globalOrder }) 
        });
        if (response.ok) {
            hasUnsavedChanges = false;
            const saveBtn = document.getElementById('saveOrderBtn');
            if (saveBtn) { saveBtn.innerHTML = 'Сохранить порядок'; saveBtn.style.background = '#27ae60'; }
            showToast('✅ Порядок сохранён', 'success');
        }
    } catch(e) { 
        console.error(e); 
        showToast('❌ Ошибка сохранения порядка', 'error');
    }
}

function toggleDebug() { 
    debugMode = !debugMode; 
    const div = document.getElementById('debugInfo'); 
    if(div) { 
        div.style.display = debugMode ? 'block' : 'none'; 
        if(debugMode) updateDebugInfo(); 
    } 
}

function updateDebugInfo() { 
    const div = document.getElementById('debugInfo'); 
    if(div) {
        const totalVacancies = Object.keys(vacancyData).length;
        div.innerHTML = `<strong>Отладка:</strong><br>- Объектов: ${objects.length}<br>- Вакансий (текущие): ${totalVacancies}<br>- Время: ${new Date().toLocaleString()}`; 
    }
}

function createElementFromHtml(html) { 
    const div = document.createElement('div'); 
    div.innerHTML = html.trim(); 
    return div.firstChild; 
}

function closeRequirementsModal() { 
    document.getElementById('requirementsModal')?.remove(); 
}

function escapeHtml(str) { 
    if(!str) return ''; 
    return str.replace(/[&<>]/g, function(m) { 
        if(m === '&') return '&amp;'; 
        if(m === '<') return '&lt;'; 
        if(m === '>') return '&gt;'; 
        return m;
    }); 
}

function escapeUrl(str) { 
    if(!str) return '#'; 
    return str; 
}

// ========== ДОБАВЛЕНИЕ ОБЪЕКТА ==========
function showAddObjectModal() {
    let modal = document.getElementById('addObjectModal');
    if (modal) modal.remove();
    
    modal = document.createElement('div');
    modal.id = 'addObjectModal';
    modal.style.cssText = 'position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); background:white; padding:25px; border-radius:12px; box-shadow:0 4px 20px rgba(0,0,0,0.3); z-index:1002; min-width:350px;';
    modal.innerHTML = `
        <h3 style="margin-top:0;">➕ Добавить объект</h3>
        <div style="margin-bottom:15px;">
            <label>Название объекта:</label>
            <input type="text" id="newObjName" style="width:100%; padding:8px; margin-top:5px; border:1px solid #ddd; border-radius:4px;">
        </div>
        <div style="margin-bottom:15px;">
            <label>Должности:</label>
            <div id="positionsContainer">
                <div style="display:flex; gap:8px; margin-bottom:8px;">
                    <input type="text" class="position-input" placeholder="Название должности" style="flex:1; padding:6px; border:1px solid #ddd; border-radius:4px;">
                    <button type="button" class="remove-pos-btn" style="display:none;">✕</button>
                </div>
            </div>
            <button type="button" onclick="addPositionFieldModal()" style="margin-top:8px; background:#3498db; color:white; border:none; padding:5px 12px; border-radius:4px; cursor:pointer;">+ Добавить должность</button>
        </div>
        <div style="text-align:right;">
            <button onclick="closeAddObjectModal()" style="background:#6c757d; color:white; border:none; padding:8px 20px; border-radius:4px; margin-right:10px;">Отмена</button>
            <button onclick="createNewObject()" style="background:#27ae60; color:white; border:none; padding:8px 20px; border-radius:4px;">Создать</button>
        </div>
    `;
    document.body.appendChild(modal);
}

function addPositionFieldModal() {
    const container = document.getElementById('positionsContainer');
    const div = document.createElement('div');
    div.style.cssText = 'display:flex; gap:8px; margin-bottom:8px;';
    div.innerHTML = `
        <input type="text" class="position-input" placeholder="Название должности" style="flex:1; padding:6px; border:1px solid #ddd; border-radius:4px;">
        <button type="button" class="remove-pos-btn" onclick="this.parentElement.remove()" style="background:#e74c3c; color:white; border:none; padding:4px 10px; border-radius:4px; cursor:pointer;">✕</button>
    `;
    container.appendChild(div);
}

function closeAddObjectModal() {
    const modal = document.getElementById('addObjectModal');
    if (modal) modal.remove();
}

async function createNewObject() {
    const name = document.getElementById('newObjName')?.value.trim();
    if (!name) {
        showToast('Введите название объекта', 'error');
        return;
    }
    
    const positionInputs = document.querySelectorAll('#positionsContainer .position-input');
    const positions = [];
    for (let input of positionInputs) {
        const posName = input.value.trim();
        if (posName) positions.push(posName);
    }
    
    if (positions.length === 0) {
        showToast('Добавьте хотя бы одну должность', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/requirements/object', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ name })
        });
        
        if (!response.ok) {
            const err = await response.json();
            showToast('Ошибка: ' + (err.error || 'Не удалось создать объект'), 'error');
            return;
        }
        
        for (const posName of positions) {
            await fetch('/api/requirements/position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ object_name: name, position_name: posName })
            });
        }
        
        vacancyData[name] = {
            rf: { men: 0, women: 0, family: 0 },
            cis: { men: 0, women: 0, family: 0 },
            positions: positions.map(p => ({ 
                name: p, 
                rf: { men:0, women:0, family:0 }, 
                cis: { men:0, women:0, family:0 },
                is_high: false
            })),
            is_high: false
        };
        
        showToast(`Объект "${name}" создан`, 'success');
        closeAddObjectModal();
        renderRequirementsTable();
    } catch (error) {
        console.error('Ошибка:', error);
        showToast('Ошибка создания объекта', 'error');
    }
}

function showAddPositionModal(objectName) {
    let modal = document.getElementById('addPositionModal');
    if (modal) modal.remove();
    
    modal = document.createElement('div');
    modal.id = 'addPositionModal';
    modal.style.cssText = 'position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); background:white; padding:25px; border-radius:12px; box-shadow:0 4px 20px rgba(0,0,0,0.3); z-index:1002; min-width:300px;';
    modal.innerHTML = `
        <h3 style="margin-top:0;">➕ Добавить должность</h3>
        <div style="margin-bottom:15px;">
            <label>Объект: <strong>${escapeHtml(objectName)}</strong></label>
        </div>
        <div style="margin-bottom:15px;">
            <label>Название должности:</label>
            <input type="text" id="newPositionName" style="width:100%; padding:8px; margin-top:5px; border:1px solid #ddd; border-radius:4px;">
        </div>
        <div style="text-align:right;">
            <button onclick="closeAddPositionModal()" style="background:#6c757d; color:white; border:none; padding:8px 20px; border-radius:4px; margin-right:10px;">Отмена</button>
            <button onclick="createNewPosition('${escapeHtml(objectName)}')" style="background:#27ae60; color:white; border:none; padding:8px 20px; border-radius:4px;">Создать</button>
        </div>
    `;
    document.body.appendChild(modal);
}

function closeAddPositionModal() {
    const modal = document.getElementById('addPositionModal');
    if (modal) modal.remove();
}

async function createNewPosition(objectName) {
    const positionName = document.getElementById('newPositionName')?.value.trim();
    if (!positionName) {
        showToast('Введите название должности', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/requirements/position', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ object_name: objectName, position_name: positionName })
        });
        
        if (!response.ok) {
            const err = await response.json();
            showToast('Ошибка: ' + (err.error || 'Не удалось добавить должность'), 'error');
            return;
        }
        
        if (!vacancyData[objectName]) {
            vacancyData[objectName] = { rf: { men:0, women:0, family:0 }, cis: { men:0, women:0, family:0 }, positions: [], is_high: false };
        }
        
        vacancyData[objectName].positions.push({
            name: positionName,
            rf: { men: 0, women: 0, family: 0 },
            cis: { men: 0, women: 0, family: 0 },
            is_high: false
        });
        
        showToast(`Должность "${positionName}" добавлена`, 'success');
        closeAddPositionModal();
        renderRequirementsTable();
    } catch (error) {
        console.error('Ошибка:', error);
        showToast('Ошибка добавления должности', 'error');
    }
}

async function deleteObject(objectName) {
    if (!confirm(`Удалить объект "${objectName}" и все его должности?`)) return;
    
    try {
        const encodedName = encodeURIComponent(objectName);
        console.log(`Удаление объекта: ${objectName} -> ${encodedName}`);
        
        const response = await fetch(`/api/requirements/object/${encodedName}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            delete vacancyData[objectName];
            showToast(result.message || `Объект "${objectName}" удалён`, 'success');
            closeRequirementsModal();
            await loadVacancyData();
            openRequirementsModal();
        } else {
            if (response.status === 404 && vacancyData[objectName]) {
                delete vacancyData[objectName];
                showToast(`Объект "${objectName}" удалён из интерфейса`, 'warning');
                closeRequirementsModal();
                await loadVacancyData();
                openRequirementsModal();
            } else {
                showToast('Ошибка: ' + (result.error || 'Не удалось удалить'), 'error');
            }
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showToast('Ошибка удаления', 'error');
    }
}

async function deletePosition(objectName, positionName) {
    if (!confirm(`Удалить должность "${positionName}"?`)) return;
    
    try {
        const response = await fetch('/api/requirements/position', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ object_name: objectName, position_name: positionName })
        });
        
        if (response.ok) {
            const obj = vacancyData[objectName];
            if (obj) {
                const index = obj.positions.findIndex(p => p.name === positionName);
                if (index !== -1) obj.positions.splice(index, 1);
            }
            showToast(`Должность "${positionName}" удалена`, 'success');
            renderRequirementsTable();
        } else {
            const err = await response.json();
            showToast('Ошибка: ' + (err.error || 'Не удалось удалить'), 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showToast('Ошибка удаления', 'error');
    }
}

// ========== ИНИЦИАЛИЗАЦИЯ ФИЛЬТРОВ ==========
function initFilters() {
    const nationalitySelect = document.getElementById('nationality');
    const genderSelect = document.getElementById('gender');
    
    if (nationalitySelect && nationalitySelect.value === 'РФ') {
        nationalitySelect.value = 'все';
    }
    if (genderSelect && genderSelect.value === '') {
        genderSelect.value = 'все';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initFilters();
    loadCurrentUserProfile(); // Загружаем профиль при загрузке страницы
});

// Глобальные функции
window.flipCard = flipCard;
window.toggleDebug = toggleDebug;
window.saveGlobalOrder = saveGlobalOrder;
window.openRequirementsModal = openRequirementsModal;
window.closeRequirementsModal = closeRequirementsModal;
window.saveAllData = saveAllData;
window.loadSelectionData = loadSelectionData;
window.filterAndDisplayObjects = filterAndDisplayObjects;
window.showAddObjectModal = showAddObjectModal;
window.closeAddObjectModal = closeAddObjectModal;
window.createNewObject = createNewObject;
window.addPositionFieldModal = addPositionFieldModal;
window.showAddPositionModal = showAddPositionModal;
window.closeAddPositionModal = closeAddPositionModal;
window.createNewPosition = createNewPosition;
window.deleteObject = deleteObject;
window.deletePosition = deletePosition;
window.openDirectionForm = openDirectionForm;
window.closeDirectionModal = closeDirectionModal;
window.addFileInput = addFileInput;
window.submitDirection = submitDirection;