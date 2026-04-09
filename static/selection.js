// static/selection.js - НОВАЯ ВЕРСИЯ (без Google Sheets)
// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
let objects = [];
let vacancyData = {};
let globalOrder = [];
let debugMode = false;
let hasUnsavedChanges = false;
let currentUserRole = null;
let currentVacancyDate = new Date().toISOString().split('T')[0];

// ========== ЗАГРУЗКА ДАННЫХ ==========
async function loadSelectionData() {
    try {
        console.log('Загрузка данных для подбора объектов...');
        
        const userResponse = await fetch('/api/auth/me', { credentials: 'include' });
        if (userResponse.ok) {
            const userData = await userResponse.json();
            currentUserRole = userData.role;
            window.currentUserRole = userData.role;
            window.isAdmin = (userData.role === 'admin' || userData.is_system_admin);
        }
        
        const resultsContainer = document.getElementById('results');
        if (resultsContainer) {
            resultsContainer.innerHTML = '<div class="loading">Загрузка объектов...</div>';
        }
        
        const response = await fetch('/api/selection/settings', { credentials: 'include' });
        const data = await response.json();
        
        if (data.error) {
            showNotification('Ошибка загрузки данных: ' + escapeHtml(data.error), 'error');
            return;
        }
        
        objects = data.objects || [];
        globalOrder = data.globalOrder || [];
        
        // Загружаем данные вакансий из БД
        await loadVacancyData();
        
        if (window.isAdmin) {
            const adminControls = document.getElementById('adminControls');
            if (adminControls) adminControls.style.display = 'block';
        }
        
        filterAndDisplayObjects();
        initDragAndDrop();
        if (debugMode) updateDebugInfo();
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        showNotification('Ошибка загрузки данных', 'error');
    }
}

async function loadVacancyData() {
    try {
        const response = await fetch(`/api/requirements/vacancy?date=${currentVacancyDate}`, { 
            credentials: 'include' 
        });
        const data = await response.json();
        
        if (!data.error) {
            vacancyData = data.data || {};
        }
    } catch (error) {
        console.error('Ошибка загрузки вакансий:', error);
    }
}

function filterAndDisplayObjects() {
    const age = parseInt(document.getElementById('age')?.value || 25);
    const gender = document.getElementById('gender')?.value || 'все';
    const nationality = document.getElementById('nationality')?.value || 'РФ';
    const hasConviction = document.getElementById('hasConviction')?.value === 'true';
    
    const filtered = objects.filter(obj => {
        if (!obj.visible) return false;
        
        const ageMatch = age >= obj.ageMin && age <= obj.ageMax;
        if (!ageMatch) return false;
        
        let nationalityMatch = false;
        if (nationality === 'РФ') {
            nationalityMatch = obj.allowedNationalities?.includes('РФ');
        } else if (nationality === 'СНГ') {
            nationalityMatch = obj.allowedNationalities?.includes('СНГ');
        } else if (nationality === 'РБ') {
            nationalityMatch = obj.allowedNationalities?.includes('РБ');
        } else {
            nationalityMatch = true;
        }
        if (!nationalityMatch) return false;
        
        const convictionMatch = hasConviction ? obj.allowsConviction : true;
        if (!convictionMatch) return false;
        
        const stats = getVacancyStats(obj.name);
        const totalMen = stats.rf.men + stats.cis.men;
        const totalWomen = stats.rf.women + stats.cis.women;
        const totalFamily = stats.rf.family + stats.cis.family;
        
        if (gender === 'все') return (totalMen > 0 || totalWomen > 0 || totalFamily > 0);
        if (gender === 'мужчина') return obj.allowedGenders?.includes('мужчина') && totalMen > 0;
        if (gender === 'женщина') return obj.allowedGenders?.includes('женщина') && totalWomen > 0;
        if (gender === 'семейные') return totalFamily > 0;
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
    if (countDisplay) {
        countDisplay.textContent = `Найдено объектов: ${sorted.length} (${priorityCount} в приоритете)`;
    }
    
    container.innerHTML = '';
    if (sorted.length === 0) {
        container.innerHTML = '<div class="no-results">По заданным критериям объектов не найдено</div>';
        return;
    }
    
    sorted.forEach((obj, idx) => {
        const stats = getVacancyStats(obj.name);
        const totalMen = stats.rf.men + stats.cis.men;
        const totalWomen = stats.rf.women + stats.cis.women;
        const totalFamily = stats.rf.family + stats.cis.family;
        
        const card = document.createElement('div');
        card.className = `flip-card ${obj.priority ? 'priority-card' : ''}`;
        card.setAttribute('data-id', obj.id);
        
        const orderNumber = window.isAdmin ? `<span class="order-badge">${idx + 1}</span>` : '';
        const dragHandle = window.isAdmin ? '<div class="drag-handle-main">⋮⋮</div>' : '';
        const safeLink = escapeUrl(obj.link);
        
        let nationalityText = '';
        if (obj.allowedNationalities?.length > 0) {
            if (obj.allowedNationalities.includes('РФ') && obj.allowedNationalities.includes('СНГ')) {
                nationalityText = 'РФ + СНГ';
            } else if (obj.allowedNationalities.includes('РФ') && obj.allowedNationalities.includes('РБ')) {
                nationalityText = 'РФ + РБ';
            } else {
                nationalityText = obj.allowedNationalities.join(', ');
            }
        }
        
        card.innerHTML = `
            <div class="flip-card-inner">
                <div class="flip-card-front">
                    ${dragHandle}
                    <h3>${orderNumber}<a href="${safeLink}" target="_blank">${escapeHtml(obj.name)}</a>${obj.priority ? ' 🔴' : ''}</h3>
                    <div class="vacancy-stats">
                        <div class="vacancy-stat"><div class="vacancy-value vacancy-men">${totalMen}</div><div class="vacancy-label">Мужчины</div></div>
                        <div class="vacancy-stat"><div class="vacancy-value vacancy-women">${totalWomen}</div><div class="vacancy-label">Женщины</div></div>
                        <div class="vacancy-stat"><div class="vacancy-value vacancy-family">${totalFamily}</div><div class="vacancy-label">Семьи</div></div>
                    </div>
                    <p><strong>Возраст:</strong> ${obj.ageMin} - ${obj.ageMax} лет</p>
                    <p><strong>Гражданство:</strong> ${nationalityText}</p>
                    <p><strong>Судимость:</strong> ${obj.allowsConviction ? 'Принимают' : 'Не принимают'}</p>
                    <button class="flip-btn" onclick="flipCard(this)">Подробнее о должностях</button>
                </div>
                <div class="flip-card-back">
                    <h3>${orderNumber}${escapeHtml(obj.name)} - Должности</h3>
                    <div class="positions-list">
                        ${stats.positions?.map(p => `<div class="position-item"><strong>${escapeHtml(p.name)}</strong></div>`).join('') || '<div>Нет должностей</div>'}
                    </div>
                    <button class="flip-btn" onclick="flipCard(this)">Назад</button>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

// ========== ГЛАВНОЕ МОДАЛЬНОЕ ОКНО С ТАБЛИЦЕЙ ==========
async function openRequirementsModal() {
    if (!window.isAdmin) {
        showNotification('Только администратор может управлять потребностями', 'error');
        return;
    }
    
    let modal = document.getElementById('requirementsModal');
    if (modal) modal.remove();
    
    showNotification('Загрузка...', 'info');
    
    try {
        // Загружаем актуальные данные из БД
        await loadVacancyData();
        renderRequirementsTable();
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('Ошибка загрузки', 'error');
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
                        <input type="date" id="vacancyDateFilter" value="${currentVacancyDate}" 
                               onchange="changeVacancyDate()" style="padding:6px; border-radius:4px; border:none; margin-right:10px;">
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
        
        // Вычисляем итоги
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
        
        // Получаем приоритет из БД потребностей
        const objFromList = objects.find(o => o.name === objName);
        const isPriority = objFromList?.priority || false;
        
        // Строки должностей
        for (let i = 0; i < positions.length; i++) {
            const pos = positions[i];
            const rowTotal = (pos.rf?.men||0) + (pos.rf?.women||0) + (pos.rf?.family||0) + 
                           (pos.cis?.men||0) + (pos.cis?.women||0) + (pos.cis?.family||0);
            
            tableHtml += `<tr data-obj="${escapeHtml(objName)}" data-pos="${escapeHtml(pos.name)}">
                ${i === 0 ? `<td rowspan="${rowCount}" style="vertical-align:middle; background:#f9f9f9;">
                    ${escapeHtml(objName)}
                    <button onclick="deleteObject('${escapeHtml(objName)}')" style="display:block; margin-top:8px; background:#e74c3c; color:white; border:none; padding:3px 8px; border-radius:3px; font-size:11px; cursor:pointer;">🗑 Удалить объект</button>
                    <button onclick="showAddPositionModal('${escapeHtml(objName)}')" style="display:block; margin-top:5px; background:#3498db; color:white; border:none; padding:3px 8px; border-radius:3px; font-size:11px; cursor:pointer;">+ Добавить должность</button>
                </div>` : ''}
                <td>${escapeHtml(pos.name)} <button onclick="deletePosition('${escapeHtml(objName)}','${escapeHtml(pos.name)}')" style="margin-left:8px; background:#e74c3c; color:white; border:none; padding:2px 6px; border-radius:3px; font-size:10px; cursor:pointer;">✕</button></td>
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
        
        // Итоговая строка
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
                        <tfoot><tr style="background:#2c3e50; color:white;"><td colspan="8" style="text-align:right;"><strong>ОБЩИЙ ИТОГ:</strong></td><td style="text-align:center;"><strong>${grandTotal}</strong></td><td></td></tr></tfoot>
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
    
    // Обработчики для автоматического пересчёта
    document.querySelectorAll('.editable').forEach(field => {
        field.addEventListener('input', function() { 
            updateRowTotals(this.getAttribute('data-obj')); 
        });
    });
}

function changeVacancyDate() {
    const dateInput = document.getElementById('vacancyDateFilter');
    if (dateInput) {
        currentVacancyDate = dateInput.value;
        loadVacancyData().then(() => {
            renderRequirementsTable();
        });
    }
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
    
    // Обновляем итоговую строку объекта
    const tbody = rows[0]?.closest('tbody');
    const totalRow = tbody?.querySelector(`tr:has(td:first-child:contains("📊 ВСЕГО:"))`);
    if (totalRow) {
        const cells = totalRow.cells;
        cells[1].querySelector('input').value = totals.rfMen;
        cells[2].querySelector('input').value = totals.rfWomen;
        cells[3].querySelector('input').value = totals.rfFamily;
        cells[4].querySelector('input').value = totals.cisMen;
        cells[5].querySelector('input').value = totals.cisWomen;
        cells[6].querySelector('input').value = totals.cisFamily;
        const totalAll = totals.rfMen + totals.rfWomen + totals.rfFamily + totals.cisMen + totals.cisWomen + totals.cisFamily;
        cells[7].textContent = totalAll;
    }
    
    // Обновляем общий итог
    updateGrandTotal();
}

function updateGrandTotal() {
    let grandTotal = 0;
    document.querySelectorAll('tr[style*="background:#f0f0f0"] td:last-child').forEach(cell => {
        const val = parseInt(cell.textContent) || 0;
        grandTotal += val;
    });
    const footerCell = document.querySelector('tfoot td:last-child');
    if (footerCell) footerCell.textContent = grandTotal;
}

// ========== МОДАЛЬНОЕ ОКНО ДОБАВЛЕНИЯ ОБЪЕКТА ==========
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
        showNotification('Введите название объекта', 'error');
        return;
    }
    
    const positionInputs = document.querySelectorAll('#positionsContainer .position-input');
    const positions = [];
    for (let input of positionInputs) {
        const posName = input.value.trim();
        if (posName) positions.push(posName);
    }
    
    if (positions.length === 0) {
        showNotification('Добавьте хотя бы одну должность', 'error');
        return;
    }
    
    try {
        // Создаём объект в БД
        const response = await fetch('/api/requirements/object', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ name })
        });
        
        if (!response.ok) {
            const err = await response.json();
            showNotification('Ошибка: ' + (err.error || 'Не удалось создать объект'), 'error');
            return;
        }
        
        // Добавляем должности
        for (const posName of positions) {
            await fetch('/api/requirements/position', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ object_name: name, position_name: posName })
            });
        }
        
        // Обновляем vacancyData
        vacancyData[name] = {
            rf: { men: 0, women: 0, family: 0 },
            cis: { men: 0, women: 0, family: 0 },
            positions: positions.map(p => ({ 
                name: p, 
                rf: { men:0, women:0, family:0 }, 
                cis: { men:0, women:0, family:0 } 
            }))
        };
        
        showNotification(`Объект "${name}" создан с ${positions.length} должностями`, 'success');
        closeAddObjectModal();
        renderRequirementsTable();
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('Ошибка создания объекта', 'error');
    }
}

// ========== МОДАЛЬНОЕ ОКНО ДОБАВЛЕНИЯ ДОЛЖНОСТИ ==========
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
        showNotification('Введите название должности', 'error');
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
            showNotification('Ошибка: ' + (err.error || 'Не удалось добавить должность'), 'error');
            return;
        }
        
        if (!vacancyData[objectName]) {
            vacancyData[objectName] = { rf: { men:0, women:0, family:0 }, cis: { men:0, women:0, family:0 }, positions: [] };
        }
        
        vacancyData[objectName].positions.push({
            name: positionName,
            rf: { men: 0, women: 0, family: 0 },
            cis: { men: 0, women: 0, family: 0 }
        });
        
        showNotification(`Должность "${positionName}" добавлена`, 'success');
        closeAddPositionModal();
        renderRequirementsTable();
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('Ошибка добавления должности', 'error');
    }
}

// ========== УДАЛЕНИЕ ==========
async function deleteObject(objectName) {
    if (!confirm(`Удалить объект "${objectName}" и все его должности?`)) return;
    
    try {
        const response = await fetch(`/api/requirements/object/${encodeURIComponent(objectName)}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (response.ok) {
            delete vacancyData[objectName];
            showNotification(`Объект "${objectName}" удалён`, 'success');
            renderRequirementsTable();
        } else {
            const err = await response.json();
            showNotification('Ошибка: ' + (err.error || 'Не удалось удалить'), 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('Ошибка удаления', 'error');
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
            showNotification(`Должность "${positionName}" удалена`, 'success');
            renderRequirementsTable();
        } else {
            const err = await response.json();
            showNotification('Ошибка: ' + (err.error || 'Не удалось удалить'), 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('Ошибка удаления', 'error');
    }
}

// ========== СОХРАНЕНИЕ ВСЕХ ДАННЫХ ==========
async function saveAllData() {
    try {
        // Собираем все данные из таблицы
        const objectsData = {};
        
        // Сохраняем значения из editable полей
        const processedObjects = new Set();
        const editableFields = document.querySelectorAll('.editable');
        
        for (const field of editableFields) {
            const objName = field.getAttribute('data-obj');
            const posName = field.getAttribute('data-pos');
            
            if (!objectsData[objName]) {
                objectsData[objName] = { positions: [] };
                processedObjects.add(objName);
            }
            
            // Ищем или создаём должность
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
        
        // Добавляем приоритеты
        const priorityChecks = document.querySelectorAll('.priority-checkbox');
        for (const chk of priorityChecks) {
            const objName = chk.getAttribute('data-obj');
            if (objectsData[objName]) {
                objectsData[objName].is_high = chk.checked;
            }
        }
        
        // Отправляем на сервер
        const response = await fetch('/api/requirements/save-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                date: currentVacancyDate,
                objects: objectsData
            })
        });
        
        if (response.ok) {
            // Обновляем приоритеты в objects
            for (const chk of priorityChecks) {
                const objName = chk.getAttribute('data-obj');
                const obj = objects.find(o => o.name === objName);
                if (obj) obj.priority = chk.checked;
            }
            
            showNotification('✅ Все данные сохранены в базу данных', 'success');
            
            // Обновляем vacancyData из БД
            await loadVacancyData();
            
            // Обновляем отображение карточек
            filterAndDisplayObjects();
            
            setTimeout(() => closeRequirementsModal(), 500);
        } else {
            const err = await response.json();
            showNotification('❌ Ошибка: ' + (err.error || 'Не удалось сохранить'), 'error');
        }
    } catch (error) {
        console.error('Ошибка сохранения:', error);
        showNotification('❌ Ошибка сохранения', 'error');
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
            showNotification('✅ Порядок сохранён', 'success');
        }
    } catch(e) { 
        console.error(e); 
        showNotification('❌ Ошибка сохранения порядка', 'error');
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
        div.innerHTML = `<strong>Отладка:</strong><br>- Объектов: ${objects.length}<br>- Вакансий в БД: ${totalVacancies}<br>- Дата: ${currentVacancyDate}<br>- Время: ${new Date().toLocaleString()}`; 
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

function showNotification(msg, type) { 
    console.log(msg); 
    alert(msg); 
}

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
window.changeVacancyDate = changeVacancyDate;