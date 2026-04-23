// static/dashboard.js - исправленная версия с оптимизированным отчётом (без прогресс-бара)

// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
let currentDashboardData = {
    offices: null,
    comparison: null,
    summary: null
};
let isLoading = false;

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
            updateOffices(data.offices);
            currentDashboardData.offices = data.offices;
        }
        
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

function updateOffices(offices) {
    const container = document.getElementById('offices-container');
    if (!container) return;
    
    const officesConfig = [
        { key: 'agent', name: 'Агент' },
        { key: 'potok', name: 'Поток' },
        // { key: 'gorkiy52', name: 'Горький52' },
        { key: 'bishkek', name: 'Бишкек' },
        { key: 'complect', name: 'Комплект' }
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
            container.appendChild(officeElement);
        }
        
        updateOfficeContent(officeElement, office.name, data);
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

function updateOfficeContent(officeElement, name, data) {
    const safeName = escapeHtml(name);
    const currentHeader = officeElement.querySelector('.office-header');
    
    if (data.count === 0) {
        if (currentHeader) {
            const countSpan = currentHeader.querySelector('.office-count');
            if (countSpan && countSpan.textContent !== '0') {
                countSpan.textContent = '0';
            }
        }
        const existingEmpty = officeElement.querySelector('.empty-objects');
        if (!existingEmpty && !officeElement.querySelector('.office-objects')) {
            officeElement.innerHTML = `
                <div class="office-header">
                    <span class="toggle">▼</span>
                    <span class="office-name">${safeName}</span>
                    <span class="office-count">0</span>
                </div>
                <div class="empty-objects">✘ На сегодня нет сделок</div>
            `;
        }
        return;
    }
    
    let objectsHtml = '';
    for (const [objName, count] of Object.entries(data.objects)) {
        objectsHtml += `
            <div class="object-row" data-object="${escapeHtml(objName)}">
                <span class="object-name">${escapeHtml(objName)}</span>
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
    
    if (comparison.only_plan) {
        for (const [name, value] of Object.entries(comparison.only_plan)) {
            allObjects.set(name, { 
                plan: value.count || value, 
                fact: 0, 
                is_high: value.is_high || false 
            });
        }
    }
    
    const deltaSections = ['negative_delta', 'zero_delta', 'positive_delta'];
    deltaSections.forEach(section => {
        if (comparison[section]) {
            for (const [name, data] of Object.entries(comparison[section])) {
                const current = allObjects.get(name) || { plan: 0, fact: 0, is_high: false };
                current.plan = data.plan;
                current.fact = data.fact;
                current.is_high = data.is_high || false;
                allObjects.set(name, current);
            }
        }
    });
    
    if (comparison.only_fact) {
        for (const [name, factCount] of Object.entries(comparison.only_fact)) {
            const current = allObjects.get(name) || { plan: 0, fact: 0, is_high: false };
            current.fact = factCount;
            allObjects.set(name, current);
        }
    }
    
    const items = Array.from(allObjects.entries()).map(([name, data]) => ({
        name, 
        plan: data.plan, 
        fact: data.fact, 
        is_high: data.is_high
    }));
    
    items.sort((a, b) => {
        if (a.is_high && !b.is_high) return -1;
        if (!a.is_high && b.is_high) return 1;
        return a.name.localeCompare(b.name);
    });
    
    if (items.length === 0) {
        container.innerHTML = '<div class="empty-state">Нет данных для отображения</div>';
        return;
    }
    
    let html = '';
    items.forEach(item => {
        const badgeClass = getBadgeClass(item.plan, item.fact);
        html += `
            <div class="discrepancy-item" data-object="${escapeHtml(item.name)}">
                <span class="object-tag${item.is_high ? ' priority-high' : ''}">
                    ${item.is_high ? '🔴 ' : ''}${escapeHtml(item.name)}
                </span>
                <span class="badge ${badgeClass}">${item.plan} / ${item.fact}</span>
            </div>
        `;
    });
    
    container.innerHTML = html;
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

// ========== ОПТИМИЗИРОВАННАЯ ФУНКЦИЯ ВЫГРУЗКИ ОТЧЁТА ==========
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

window.manualRefresh = manualRefresh;
window.exportFullReport = exportFullReport;
window.updatePeriodDisplay = updatePeriodDisplay;
window.getReportDateRange = getReportDateRange;
window.formatPeriodDisplay = formatPeriodDisplay;
window.loadDashboardForDate = loadDashboardForDate;