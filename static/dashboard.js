// static/dashboard.js - исправленная версия с оптимизированным отчётом и отчётами по 1 смене

// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
let currentDashboardData = {
    offices: null,
    staffByObject: null,
    comparison: null,
    summary: null
};
let isLoading = false;
let currentDirectionsView = 'offices';

// ========== ИНКРЕМЕНТНАЯ ЗАГРУЗКА ДАШБОРДА ==========
async function loadDashboardForDate(dateString) {
    if (isLoading) {
        console.log('Загрузка уже выполняется, пропускаем...');
        return;
    }
    
    try {
        isLoading = true;
        
        // Показываем маленький индикатор обновления в углу
        showUpdateIndicator();
        
        const response = await fetch(`${API_BASE}/dashboard?date=${dateString}`, { 
            credentials: 'include',
            headers: {
                'Cache-Control': 'no-cache'
            }
        });
        const data = await response.json();
        
        if (data.error) {
            showError(data.error);
            hideUpdateIndicator();
            showErrorInContainers(data.error);
            return;
        }
        
        updateUpdateTime();
        
        if (data.offices) {
            updateOffices(data.offices, getPriorityObjectNames(data.comparison));
            currentDashboardData.offices = data.offices;
        }

        if (Object.prototype.hasOwnProperty.call(data, 'staff_by_object')) {
            updateStaffDirections(data.staff_by_object || {}, getPriorityObjectNames(data.comparison));
            currentDashboardData.staffByObject = data.staff_by_object || {};
        }

        switchDirectionsView(currentDirectionsView);
        
        if (data.comparison) {
            updatePlanFactTable(data.comparison);
            currentDashboardData.comparison = data.comparison;
        }
        
        if (data.summary) {
            updateSummary(data.summary);
            currentDashboardData.summary = data.summary;
        }
        
        hideUpdateIndicator();
        
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        showError('Не удалось загрузить данные');
        showErrorInContainers('Ошибка загрузки данных');
        hideUpdateIndicator();
    } finally {
        isLoading = false;
    }
}

function showErrorInContainers(message) {
    const officesContainer = document.getElementById('offices-container');
    if (officesContainer && officesContainer.innerHTML.includes('Загрузка')) {
        officesContainer.innerHTML = `<div class="error-state">❌ ${escapeHtml(message)}</div>`;
    }
    
    const planFactContainer = document.getElementById('plan-fact-container');
    if (planFactContainer && planFactContainer.innerHTML.includes('Загрузка')) {
        planFactContainer.innerHTML = `<div class="error-state">❌ ${escapeHtml(message)}</div>`;
    }
    
    const summaryContainer = document.getElementById('summary-container');
    if (summaryContainer && summaryContainer.innerHTML.includes('Загрузка')) {
        summaryContainer.innerHTML = `<div class="error-state">❌ ${escapeHtml(message)}</div>`;
    }
}

function compareObjectNames(a, b) {
    return a.localeCompare(b, 'ru', { sensitivity: 'base' });
}

function getPriorityObjectNames(comparison) {
    const priorityNames = new Set();
    if (!comparison) return priorityNames;

    const sections = ['only_plan', 'negative_delta', 'zero_delta', 'positive_delta'];
    sections.forEach(section => {
        for (const [name, data] of Object.entries(comparison[section] || {})) {
            if (data && typeof data === 'object' && data.is_high) {
                priorityNames.add(name);
            }
        }
    });

    return priorityNames;
}

function updateOffices(offices, priorityNames = new Set()) {
    const container = document.getElementById('offices-container');
    if (!container) return;
    
    const officesConfig = [
        { key: 'agent', name: 'Агент' },
        { key: 'bishkek', name: 'Бишкек' },
        { key: 'complect', name: 'Комплект' },
        { key: 'potok', name: 'Поток' },
        { key: 'service', name: 'Сервис' }
    ];
    
    let hasData = false;
    
    officesConfig.forEach(office => {
        const data = offices[office.key] || { count: 0, objects: {} };
        if (data.count > 0) hasData = true;
        
        let officeElement = container.querySelector(`[data-office="${office.key}"]`);
        
        if (!officeElement) {
            officeElement = document.createElement('div');
            officeElement.className = 'office-item';
            officeElement.setAttribute('data-office', office.key);
        }

        container.appendChild(officeElement);
        updateOfficeContent(officeElement, office.name, data, priorityNames);
    });
    
    const noDataImage = document.getElementById('noDataImage');
    if (noDataImage) {
        noDataImage.style.display = hasData ? 'none' : 'block';
    }
    
    const loadingElement = container.querySelector('.loading');
    if (loadingElement) {
        loadingElement.remove();
    }
}

function updateOfficeContent(officeElement, name, data, priorityNames = new Set()) {
    const safeName = escapeHtml(name);
    
    if (data.count === 0) {
        officeElement.innerHTML = `
            <div class="office-header">
                <span class="toggle">▼</span>
                <span class="office-name">${safeName}</span>
                <span class="office-count">0</span>
            </div>
            <div class="empty-objects">Нет направлений за выбранную дату</div>
        `;
        return;
    }
    
    let objectsHtml = '';
    const sortedObjects = Object.entries(data.objects).sort(([nameA], [nameB]) => (
        compareObjectNames(nameA, nameB)
    ));

    for (const [objName, count] of sortedObjects) {
        const isPriority = priorityNames.has(objName);
        objectsHtml += `
            <div class="object-row" data-object="${escapeHtml(objName)}">
                <span class="object-name${isPriority ? ' priority-high' : ''}">
                    ${isPriority ? '🔴 ' : ''}${escapeHtml(objName)}
                </span>
                <span class="object-value">${count}</span>
            </div>
        `;
    }
    
    officeElement.innerHTML = `
        <div class="office-header">
            <span class="toggle">▼</span>
            <span class="office-name">${safeName}</span>
            <span class="office-count">${data.count}</span>
        </div>
        <div class="office-objects">${objectsHtml}</div>
    `;
}

function updatePlanFactTable(comparison) {
    const container = document.getElementById('plan-fact-container');
    if (!container) return;

    const allObjects = new Map();

    if (comparison.plan_changes) {
        for (const [name, data] of Object.entries(comparison.plan_changes)) {
            allObjects.set(name, {
                plan: data.current || 0,
                planChange: data.change || 0,
                fact: 0,
                is_high: data.is_high || false
            });
        }
    }

    if (comparison.only_plan) {
        for (const [name, value] of Object.entries(comparison.only_plan)) {
            const current = allObjects.get(name) || {};
            allObjects.set(name, {
                ...current,
                plan: value.count || value,
                planChange: current.planChange || 0,
                fact: current.fact || 0,
                is_high: value.is_high || false
            });
        }
    }

    const deltaSections = ['negative_delta', 'zero_delta', 'positive_delta'];
    deltaSections.forEach(section => {
        if (comparison[section]) {
            for (const [name, data] of Object.entries(comparison[section])) {
                const current = allObjects.get(name) || { plan: 0, planChange: 0, fact: 0, is_high: false };
                current.plan = data.plan;
                current.fact = data.fact;
                current.is_high = data.is_high || false;
                allObjects.set(name, current);
            }
        }
    });
    
    if (comparison.only_fact) {
        for (const [name, factCount] of Object.entries(comparison.only_fact)) {
            const current = allObjects.get(name) || { plan: 0, planChange: 0, fact: 0, is_high: false };
            current.fact = factCount;
            allObjects.set(name, current);
        }
    }

    const items = Array.from(allObjects.entries()).map(([name, data]) => ({
        name,
        plan: data.plan || 0,
        planChange: data.planChange || 0,
        fact: data.fact || 0,
        is_high: data.is_high
    }));

    items.sort((a, b) => {
        if (a.is_high && !b.is_high) return -1;
        if (!a.is_high && b.is_high) return 1;
        return compareObjectNames(a.name, b.name);
    });

    if (items.length === 0) {
        container.innerHTML = '<div class="empty-state">Нет данных для отображения</div>';
        return;
    }

    let html = `
        <div class="plan-fact-table-wrap">
            <table class="plan-fact-table">
                <thead>
                    <tr>
                        <th>Название объекта</th>
                        <th>Дельта от вчера</th>
                        <th>План</th>
                        <th>Факт</th>
                    </tr>
                </thead>
                <tbody>
    `;

    items.forEach(item => {
        const changeSign = item.planChange > 0 ? '+' : '';
        const changeClass = item.planChange > 0
            ? 'plan-change-up'
            : item.planChange < 0 ? 'plan-change-down' : 'plan-change-zero';

        html += `
            <tr data-object="${escapeHtml(item.name)}" class="${item.is_high ? 'priority-row' : ''}">
                <td class="plan-fact-name">${escapeHtml(item.name)}</td>
                <td class="${changeClass}">${changeSign}${item.planChange}</td>
                <td>${item.plan}</td>
                <td>${item.fact}</td>
            </tr>
        `;
    });

    const totals = items.reduce((result, item) => {
        result.planChange += item.planChange;
        result.plan += item.plan;
        result.fact += item.fact;
        return result;
    }, { planChange: 0, plan: 0, fact: 0 });
    const totalChangeSign = totals.planChange > 0 ? '+' : '';
    const totalChangeClass = totals.planChange > 0
        ? 'plan-change-up'
        : totals.planChange < 0 ? 'plan-change-down' : 'plan-change-zero';

    html += `
                </tbody>
                <tfoot>
                    <tr>
                        <td>Итого</td>
                        <td class="${totalChangeClass}">${totalChangeSign}${totals.planChange}</td>
                        <td>${totals.plan}</td>
                        <td>${totals.fact}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
    `;
    container.innerHTML = html;
}

function switchDirectionsView(view) {
    currentDirectionsView = view === 'staff' ? 'staff' : 'offices';

    const officesContainer = document.getElementById('offices-container');
    const staffContainer = document.getElementById('staff-directions-container');
    const noDataImage = document.getElementById('noDataImage');

    if (officesContainer) {
        officesContainer.style.display = currentDirectionsView === 'offices' ? 'flex' : 'none';
    }
    if (staffContainer) {
        staffContainer.style.display = currentDirectionsView === 'staff' ? 'flex' : 'none';
    }

    document.querySelectorAll('.directions-view-btn').forEach(button => {
        button.classList.toggle(
            'active',
            button.dataset.directionsView === currentDirectionsView
        );
    });

    if (noDataImage) {
        const hasOfficeData = Object.values(currentDashboardData.offices || {})
            .some(office => (office?.count || 0) > 0);
        noDataImage.style.display = (
            currentDirectionsView === 'offices' && !hasOfficeData
        ) ? 'block' : 'none';
    }
}

function updateStaffDirections(staffByObject, priorityNames = new Set()) {
    const container = document.getElementById('staff-directions-container');
    if (!container) return;

    const objectsByStaff = new Map();
    for (const [objectName, staff] of Object.entries(staffByObject || {})) {
        for (const [staffName, count] of Object.entries(staff || {})) {
            if (staffName.trim().toLocaleLowerCase('ru').startsWith('спутник')) {
                continue;
            }
            if (!objectsByStaff.has(staffName)) {
                objectsByStaff.set(staffName, new Map());
            }
            const objects = objectsByStaff.get(staffName);
            objects.set(objectName, (objects.get(objectName) || 0) + count);
        }
    }

    const employees = Array.from(objectsByStaff, ([staffName, objects]) => ({
            staffName,
            objects: Array.from(objects).sort(([nameA], [nameB]) => (
                compareObjectNames(nameA, nameB)
            ))
        }))
        .sort((a, b) => compareObjectNames(a.staffName, b.staffName));

    if (employees.length === 0) {
        container.innerHTML = '<div class="empty-state">Нет направлений с указанным сотрудником</div>';
        return;
    }

    container.innerHTML = employees.map(item => {
        const total = item.objects.reduce((sum, [, count]) => sum + count, 0);
        const objectRows = item.objects.map(([objectName, count]) => `
            <div class="object-row">
                <span class="object-name${priorityNames.has(objectName) ? ' priority-high' : ''}">${priorityNames.has(objectName) ? '🔴 ' : ''}${escapeHtml(objectName)}</span>
                <span class="object-value">${count}</span>
            </div>
        `).join('');

        return `
            <div class="office-item">
                <div class="office-header">
                    <span class="toggle">▼</span>
                    <span class="office-name"><i class="fas fa-user"></i> ${escapeHtml(item.staffName)}</span>
                    <span class="office-count">${total}</span>
                </div>
                <div class="office-objects">${objectRows}</div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('.office-header').forEach(header => {
        header.addEventListener('click', function() {
            const rows = this.nextElementSibling;
            const toggle = this.querySelector('.toggle');
            const isCollapsed = rows.style.display === 'none';
            rows.style.display = isCollapsed ? 'flex' : 'none';
            toggle.textContent = isCollapsed ? '▼' : '▶';
        });
    });
}

function updateSummary(summary) {
    const container = document.getElementById('summary-container');
    if (!container) return;
    
    const deltaSign = summary.delta >= 0 ? '+' : '';
    const deltaClass = summary.delta >= 0 ? 'green' : 'red';
    
    container.innerHTML = `
        <div class="summary-row">
            <span>Всего нужно сегодня:</span>
            <span class="summary-value summary-total-plan">${summary.total_plan || 0} чел.</span>
        </div>
        <div class="summary-row">
            <span>Всего направлено сегодня:</span>
            <span class="summary-value summary-total-fact">${summary.total_fact || 0} чел.</span>
        </div>
        <div class="summary-row">
            <span>Дельта:</span>
            <span class="summary-value summary-delta ${deltaClass}">${deltaSign}${summary.delta || 0}</span>
        </div>
        <div class="summary-row">
            <span>Обеспечено:</span>
            <span class="summary-value summary-percent">${summary.percent || 0}%</span>
        </div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: ${Math.min(summary.percent || 0, 100)}%;"></div>
        </div>
    `;
}

function showUpdateIndicator() {
    let indicator = document.getElementById('update-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'update-indicator';
        indicator.className = 'update-indicator';
        indicator.innerHTML = '🔄 Обновление...';
        document.body.appendChild(indicator);
    }
    indicator.style.display = 'block';
    indicator.style.opacity = '1';
}

function hideUpdateIndicator() {
    const indicator = document.getElementById('update-indicator');
    if (indicator) {
        indicator.style.opacity = '0';
        setTimeout(() => {
            if (indicator) indicator.style.display = 'none';
        }, 300);
    }
}

function updateUpdateTime() {
    const updateTime = document.getElementById('update-time');
    if (updateTime) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        updateTime.textContent = `Обновлено: ${timeStr}`;
    }
}

function getBadgeClass(plan, fact) {
    if (fact < plan) return 'badge-red';
    if (fact > plan) return 'badge-green';
    if (fact === plan && plan > 0) return 'badge-purple';
    return 'badge-neutral';
}

async function exportFullReport() {
    const { fromDate, toDate } = getReportDateRange();
    
    const exportBtn = document.getElementById('export-full-report');
    if (!exportBtn) return;
    
    const originalText = exportBtn.innerHTML;
    exportBtn.disabled = true;
    exportBtn.innerHTML = '<span class="refresh-icon">↻</span> Загрузка...';
    
    try {
        const response = await fetch(`/api/report?from=${fromDate}&to=${toDate}`, { 
            credentials: 'include',
            headers: {
                'Cache-Control': 'no-cache'
            }
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const data = await response.json();
        
        if (data.error) throw new Error(data.error);
        
        const headers = [
            'Дата', 
            'Объект', 
            'План', 
            'Приоритет',
            'Комплект', 
            'Поток', 
            'Горький52', 
            'Агент', 
            'Бишкек',
            'Всего направлено'
        ];
        
        const rows = [];
        
        for (const day of data) {
            for (const [obj, stats] of Object.entries(day.objects || {})) {
                const totalSent = (stats.complect || 0) + (stats.potok || 0) + 
                                  (stats.gorkiy || 0) + (stats.agent || 0) + 
                                  (stats.bishkek || 0);
                
                if (stats.plan === 0 && totalSent === 0) continue;
                
                rows.push([
                    day.date,
                    obj,
                    stats.plan || 0,
                    stats.is_high ? '🔥 ПРИОРИТЕТ' : '',
                    stats.complect || 0,
                    stats.potok || 0,
                    stats.gorkiy || 0,
                    stats.agent || 0,
                    stats.bishkek || 0,
                    totalSent
                ]);
            }
        }
        
        rows.sort((a, b) => {
            if (a[3] && !b[3]) return -1;
            if (!a[3] && b[3]) return 1;
            const dateCompare = a[0].localeCompare(b[0]);
            if (dateCompare !== 0) return dateCompare;
            return a[1].localeCompare(b[1]);
        });
        
        if (rows.length === 0) {
            showNotification('⚠️ Нет данных для выгрузки за выбранный период', 'warning');
            return;
        }
        
        const csvContent = [headers.join(';'), ...rows.map(r => r.join(';'))].join('\n');
        const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `report_${fromDate}_${toDate}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showNotification(`✅ Отчёт выгружен (${rows.length} записей)`, 'success');
    } catch (error) {
        console.error('Ошибка выгрузки отчёта:', error);
        showNotification('❌ Не удалось выгрузить отчёт: ' + error.message, 'error');
    } finally {
        exportBtn.disabled = false;
        exportBtn.innerHTML = originalText;
    }
}

function getReportDateRange() {
    const from = document.getElementById('report-from')?.value || getTodayDate();
    const to = document.getElementById('report-to')?.value || getTodayDate();
    return { fromDate: from, toDate: to };
}

function formatPeriodDisplay(fromDate, toDate) {
    const fromParts = fromDate.split('-');
    const toParts = toDate.split('-');
    const fromStr = `${fromParts[2]}.${fromParts[1]}.${fromParts[0]}`;
    const toStr = `${toParts[2]}.${toParts[1]}.${toParts[0]}`;
    return fromDate === toDate ? fromStr : `${fromStr} - ${toStr}`;
}

function updatePeriodDisplay() {
    const { fromDate, toDate } = getReportDateRange();
    const periodDisplay = document.getElementById('periodDisplay');
    if (periodDisplay) {
        periodDisplay.textContent = formatPeriodDisplay(fromDate, toDate);
    }
}

// ========== ПЕРЕКЛЮЧЕНИЕ ВНУТРЕННИХ ВКЛАДОК ДАШБОРДА ==========
function switchDashboardInnerTab(tabName) {
    // Скрываем все контейнеры
    const containers = ['planFactContainer', 'firstShiftObjectContainer', 'firstShiftStaffContainer'];
    containers.forEach(containerId => {
        const el = document.getElementById(containerId);
        if (el) {
            el.classList.remove('active');
            el.style.display = 'none';
        }
    });
    
    // Показываем выбранный контейнер
    let selectedContainer = null;
    if (tabName === 'plan-fact') {
        selectedContainer = document.getElementById('planFactContainer');
        if (selectedContainer) {
            selectedContainer.style.display = 'block';
            selectedContainer.classList.add('active');
        }
        // Обновляем данные план/факт
        const date = document.getElementById('date-picker')?.value || getTodayDate();
        loadDashboardForDate(date);
    } else if (tabName === 'first-shift-object') {
        selectedContainer = document.getElementById('firstShiftObjectContainer');
        if (selectedContainer) {
            selectedContainer.style.display = 'block';
            selectedContainer.classList.add('active');
        }
        loadFirstShiftByObject();
    } else if (tabName === 'first-shift-staff') {
        selectedContainer = document.getElementById('firstShiftStaffContainer');
        if (selectedContainer) {
            selectedContainer.style.display = 'block';
            selectedContainer.classList.add('active');
        }
        loadFirstShiftByStaff();
    }
    
    // Обновляем активный класс внутренних кнопок
    document.querySelectorAll('.dashboard-inner-tab').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-inner-tab') === tabName) {
            btn.classList.add('active');
        }
    });
}

// ========== ОТЧЁТ: ОТРАБОТАВШИЕ 1 СМЕНУ ПО ОБЪЕКТАМ ==========
async function loadFirstShiftByObject() {
    const contentDiv = document.getElementById('fsObjectContent');
    const summaryDiv = document.getElementById('fsObjectSummary');
    
    let fromDate = document.getElementById('fsObjectFrom')?.value;
    let toDate = document.getElementById('fsObjectTo')?.value;
    
    if (!fromDate || !toDate) {
        const today = getTodayDate();
        fromDate = fromDate || today;
        toDate = toDate || today;
        if (document.getElementById('fsObjectFrom')) document.getElementById('fsObjectFrom').value = fromDate;
        if (document.getElementById('fsObjectTo')) document.getElementById('fsObjectTo').value = toDate;
    }
    
    contentDiv.innerHTML = '<div class="loading">Загрузка данных...</div>';
    if (summaryDiv) summaryDiv.innerHTML = '<div class="loading">Загрузка...</div>';
    
    try {
        const response = await fetch(`/api/first-shift-by-object?from=${fromDate}&to=${toDate}`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.error) {
            contentDiv.innerHTML = `<div class="error-state">❌ ${data.error}</div>`;
            return;
        }
        
        // Обновляем сводку
        if (summaryDiv) {
            summaryDiv.innerHTML = `
                <div class="summary-row">
                    <span>Период:</span>
                    <span class="summary-value">${formatDateForDisplay(fromDate)} - ${formatDateForDisplay(toDate)}</span>
                </div>
                <div class="summary-row">
                    <span>Всего сделок:</span>
                    <span class="summary-value" style="background: #ffd700; color: #2c3e50;">${data.total_all || 0}</span>
                </div>
            `;
        }
        
        renderFirstShiftByObject(data.data, data.totals);
        
    } catch (error) {
        console.error('Ошибка:', error);
        contentDiv.innerHTML = '<div class="error-state">❌ Ошибка загрузки данных</div>';
    }
}

function renderFirstShiftByObject(data, totals) {
    const container = document.getElementById('fsObjectContent');
    if (!container) return;
    
    const categories = ['Поток', 'Комплект', 'Бишкек'];
    let html = '';
    
    for (const cat of categories) {
        const catData = data[cat] || {};
        const catTotal = totals[cat] || 0;
        const items = Object.entries(catData).sort((a, b) => b[1] - a[1]);
        
        html += `
            <div class="office-item" style="margin-bottom: 20px;">
                <div class="office-header">
                    <span class="toggle">▼</span>
                    <span class="office-name">${escapeHtml(cat)}</span>
                    <span class="office-count">${catTotal}</span>
                </div>
                <div class="office-objects">
        `;
        
        if (items.length === 0) {
            html += `<div class="empty-objects">✘ Нет сделок</div>`;
        } else {
            for (const [company, count] of items) {
                html += `
                    <div class="object-row">
                        <span class="object-name">${escapeHtml(company)}</span>
                        <span class="object-value">${count}</span>
                    </div>
                `;
            }
        }
        
        html += `</div></div>`;
    }
    
    container.innerHTML = html;
    
    // Добавляем обработчики для сворачивания/разворачивания
    document.querySelectorAll('#fsObjectContent .office-header').forEach(header => {
        header.addEventListener('click', function() {
            const objectsDiv = this.nextElementSibling;
            const toggle = this.querySelector('.toggle');
            if (objectsDiv.style.display === 'none') {
                objectsDiv.style.display = 'block';
                toggle.textContent = '▼';
            } else {
                objectsDiv.style.display = 'none';
                toggle.textContent = '▶';
            }
        });
    });
}

// ========== ОТЧЁТ: ОТРАБОТАВШИЕ 1 СМЕНУ ПО СОТРУДНИКАМ ==========
async function loadFirstShiftByStaff() {
    const contentDiv = document.getElementById('fsStaffContent');
    const summaryDiv = document.getElementById('fsStaffSummary');
    
    let fromDate = document.getElementById('fsStaffFrom')?.value;
    let toDate = document.getElementById('fsStaffTo')?.value;
    
    if (!fromDate || !toDate) {
        const today = getTodayDate();
        fromDate = fromDate || today;
        toDate = toDate || today;
        if (document.getElementById('fsStaffFrom')) document.getElementById('fsStaffFrom').value = fromDate;
        if (document.getElementById('fsStaffTo')) document.getElementById('fsStaffTo').value = toDate;
    }
    
    contentDiv.innerHTML = '<div class="loading">Загрузка данных...</div>';
    if (summaryDiv) summaryDiv.innerHTML = '<div class="loading">Загрузка...</div>';
    
    try {
        const response = await fetch(`/api/first-shift-by-staff?from=${fromDate}&to=${toDate}`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.error) {
            contentDiv.innerHTML = `<div class="error-state">❌ ${data.error}</div>`;
            return;
        }
        
        if (summaryDiv) {
            summaryDiv.innerHTML = `
                <div class="summary-row">
                    <span>Период:</span>
                    <span class="summary-value">${formatDateForDisplay(fromDate)} - ${formatDateForDisplay(toDate)}</span>
                </div>
                <div class="summary-row">
                    <span>Всего сделок:</span>
                    <span class="summary-value" style="background: #ffd700; color: #2c3e50;">${data.total_all || 0}</span>
                </div>
            `;
        }
        
        renderFirstShiftByStaff(data.data, data.totals);
        
    } catch (error) {
        console.error('Ошибка:', error);
        contentDiv.innerHTML = '<div class="error-state">❌ Ошибка загрузки данных</div>';
    }
}

function renderFirstShiftByStaff(data, totals) {
    const container = document.getElementById('fsStaffContent');
    if (!container) return;
    
    const categories = ['Поток', 'Комплект', 'Сервис', 'Спутник', 'Бишкек'];
    let html = '';
    
    for (const cat of categories) {
        const catData = data[cat] || {};
        const catTotal = totals[cat] || 0;
        const items = Object.entries(catData).sort((a, b) => b[1] - a[1]);
        
        html += `
            <div class="office-item" style="margin-bottom: 20px;">
                <div class="office-header">
                    <span class="toggle">▼</span>
                    <span class="office-name">${escapeHtml(cat)}</span>
                    <span class="office-count">${catTotal}</span>
                </div>
                <div class="office-objects">
        `;
        
        if (items.length === 0) {
            html += `<div class="empty-objects">✘ Нет сделок</div>`;
        } else {
            for (const [staff, count] of items) {
                html += `
                    <div class="object-row">
                        <span class="object-name"><i class="fas fa-user"></i> ${escapeHtml(staff)}</span>
                        <span class="object-value">${count}</span>
                    </div>
                `;
            }
        }
        
        html += `</div></div>`;
    }
    
    container.innerHTML = html;
    
    // Добавляем обработчики для сворачивания/разворачивания
    document.querySelectorAll('#fsStaffContent .office-header').forEach(header => {
        header.addEventListener('click', function() {
            const objectsDiv = this.nextElementSibling;
            const toggle = this.querySelector('.toggle');
            if (objectsDiv.style.display === 'none') {
                objectsDiv.style.display = 'block';
                toggle.textContent = '▼';
            } else {
                objectsDiv.style.display = 'none';
                toggle.textContent = '▶';
            }
        });
    });
}

// ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
function formatDateForDisplay(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length === 3) {
        return `${parts[2]}.${parts[1]}.${parts[0]}`;
    }
    return dateStr;
}

function getCompanyEmoji(companyName) {
    const emojis = {
        "ФитнесШок": "🍫",
        "Агама Лешково": "🐙",
        "Мираторг": "🥩",
        "Креветки Клинский": "🦐",
        "Мираторг Тула": "🥕",
        "Major": "👗",
        "КуулКлевер": "🍀",
        "Спортмастер": "⚽",
        "Мяснов": "🥩",
        "Сберлогистика Пушкино": "💼",
        "Клинский мясокомбинат": "🐄",
        "Цветы Раменское": "🌹",
        "Яндекс Тарный": "❄️",
        "Павловская Птицефабрика": "🐔",
        "Тамбовский бекон": "🥓",
        "Индейка Калуга": "🦃",
        "Спортмастер СПБ": "🏃",
        "СДТ": "📎",
        "БелГранКорм Новгород": "🐥",
        "METRO MGL": "🍾",
        "АртПак": "🍽️",
        "Невский Кондитер": "🍫"
    };
    for (const [key, emoji] of Object.entries(emojis)) {
        if (companyName.includes(key)) return emoji;
    }
    return "🏢";
}

// ========== ЭКСПОРТ В CSV ==========
async function exportFirstShiftByObject() {
    const fromDate = document.getElementById('fsObjectFrom')?.value || getTodayDate();
    const toDate = document.getElementById('fsObjectTo')?.value || getTodayDate();
    
    try {
        const response = await fetch(`/api/first-shift-by-object?from=${fromDate}&to=${toDate}`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.error) throw new Error(data.error);
        
        const rows = [];
        rows.push(['Категория', 'Объект', 'Количество']);
        
        for (const [cat, objects] of Object.entries(data.data)) {
            for (const [obj, count] of Object.entries(objects)) {
                rows.push([cat, obj, count]);
            }
        }
        
        rows.push([], ['ИТОГО:', '', data.total_all]);
        
        const csvContent = rows.map(row => row.join(';')).join('\n');
        const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `first_shift_by_object_${fromDate}_${toDate}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        
        showNotification(`✅ Отчёт выгружен`, 'success');
    } catch (error) {
        showNotification('❌ Ошибка выгрузки', 'error');
    }
}

async function exportFirstShiftByStaff() {
    const fromDate = document.getElementById('fsStaffFrom')?.value || getTodayDate();
    const toDate = document.getElementById('fsStaffTo')?.value || getTodayDate();
    
    try {
        const response = await fetch(`/api/first-shift-by-staff?from=${fromDate}&to=${toDate}`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (data.error) throw new Error(data.error);
        
        const rows = [];
        rows.push(['Категория', 'Сотрудник', 'Количество']);
        
        for (const [cat, staffList] of Object.entries(data.data)) {
            for (const [staff, count] of Object.entries(staffList)) {
                rows.push([cat, staff, count]);
            }
        }
        
        rows.push([], ['ИТОГО:', '', data.total_all]);
        
        const csvContent = rows.map(row => row.join(';')).join('\n');
        const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `first_shift_by_staff_${fromDate}_${toDate}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        
        showNotification(`✅ Отчёт выгружен`, 'success');
    } catch (error) {
        showNotification('❌ Ошибка выгрузки', 'error');
    }
}

// ========== ФИКСАЦИЯ ДНЯ В ОТЧЁТЕ ==========

async function fixDayInReport() {
    const datePicker = document.getElementById('date-picker');
    if (!datePicker) {
        showNotification('❌ Ошибка: не найден календарь', 'error');
        return;
    }
    
    const date = datePicker.value;
    if (!date) {
        showNotification('❌ Выберите дату для фиксации', 'error');
        return;
    }
    
    // Проверяем, есть ли уже снапшот за эту дату
    try {
        const statusResponse = await fetch(`/api/snapshot/status?from=${date}&to=${date}`, {
            credentials: 'include'
        });
        const statusData = await statusResponse.json();
        
        if (statusData.existing_count > 0) {
            if (!confirm(`Дата ${formatDateForDisplay(date)} уже зафиксирована. Перезаписать?`)) {
                return;
            }
        }
    } catch (e) {
        console.warn('Не удалось проверить статус снапшота:', e);
    }
    
    const fixBtn = document.getElementById('fixDayBtn');
    if (!fixBtn) {
        showNotification('❌ Кнопка фиксации не найдена', 'error');
        return;
    }
    
    const originalText = fixBtn.innerHTML;
    fixBtn.disabled = true;
    fixBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Фиксация...';
    fixBtn.style.opacity = '0.7';
    
    try {
        const response = await fetch('/api/fix-day', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ date: date })
        });
        
        const data = await response.json();
        
        // ВОССТАНАВЛИВАЕМ КНОПКУ ДО ПОКАЗА УВЕДОМЛЕНИЯ
        fixBtn.disabled = false;
        fixBtn.innerHTML = originalText;
        fixBtn.style.opacity = '1';
        
        if (data.success) {
            showNotification(`✅ День ${formatDateForDisplay(date)} зафиксирован! (${data.snapshots_count} записей, ${data.priority_count} приоритетных)`, 'success');
            // Обновляем данные дашборда
            await loadDashboardForDate(date);
        } else {
            showNotification(`❌ ${data.error || 'Ошибка фиксации'}`, 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        
        // ВОССТАНАВЛИВАЕМ КНОПКУ ДАЖЕ ПРИ ОШИБКЕ
        fixBtn.disabled = false;
        fixBtn.innerHTML = originalText;
        fixBtn.style.opacity = '1';
        
        showNotification('❌ Ошибка при фиксации дня', 'error');
    }
}

// Делаем функции глобальными
window.manualRefresh = manualRefresh;
window.exportFullReport = exportFullReport;
window.updatePeriodDisplay = updatePeriodDisplay;
window.getReportDateRange = getReportDateRange;
window.formatPeriodDisplay = formatPeriodDisplay;
window.loadDashboardForDate = loadDashboardForDate;
window.switchDashboardInnerTab = switchDashboardInnerTab;
window.loadFirstShiftByObject = loadFirstShiftByObject;
window.loadFirstShiftByStaff = loadFirstShiftByStaff;
window.exportFirstShiftByObject = exportFirstShiftByObject;
window.exportFirstShiftByStaff = exportFirstShiftByStaff;
window.fixDayInReport = fixDayInReport;
