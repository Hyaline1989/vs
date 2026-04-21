// static/passport_viewer.js - просмотр паспорта для менеджеров

// ========== ПРОСМОТР ПАСПОРТА ОБЪЕКТА ==========

async function viewPassport(objectId, objectName) {
    try {
        const response = await fetch(`/api/admin/objects/${objectId}/passport`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            showNotification('Ошибка загрузки паспорта', 'error');
            return;
        }
        
        const data = await response.json();
        
        // Создаём модальное окно для просмотра
        let modal = document.getElementById('passportViewModal');
        if (modal) modal.remove();
        
        modal = document.createElement('div');
        modal.id = 'passportViewModal';
        modal.className = 'modal passport-view-modal';
        modal.style.display = 'flex';
        
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 800px; width: 95%; max-height: 85vh;">
                <div class="modal-header" style="background: linear-gradient(135deg, #A42C30 0%, #C14A4E 100%);">
                    <h3><i class="fas fa-id-card"></i> Паспорт объекта: ${escapeHtml(objectName)}</h3>
                    <button class="modal-close" onclick="closePassportView()">&times;</button>
                </div>
                <div class="modal-body" style="max-height: calc(85vh - 70px); overflow-y: auto; padding: 20px;">
                    ${renderPassportContent(data, objectId)}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('Ошибка загрузки паспорта', 'error');
    }
}

function renderPassportContent(data, objectId) {
    let html = '';
    
    // Адреса
    if (data.address_production || data.address_hostel) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-map-marker-alt"></i> Адреса</h4>
                ${data.address_production ? `<div class="passport-field" style="margin-bottom: 10px;"><strong>📍 Производство:</strong><br><div style="margin-top: 5px;">${escapeHtml(data.address_production)}</div></div>` : ''}
                ${data.address_hostel ? `<div class="passport-field" style="margin-bottom: 10px;"><strong>🏠 Хостел:</strong><br><div style="margin-top: 5px;">${escapeHtml(data.address_hostel)}</div></div>` : ''}
            </div>
        `;
    }
    
    // Операция/ставка (с HTML)
    if (data.operation_rate) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-chart-line"></i> Операция / Ставка</h4>
                <div class="passport-field passport-html" style="margin-top: 5px;">${data.operation_rate}</div>
            </div>
        `;
    }
    
    // Требования
    if (data.requirements) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-user-check"></i> Требования к кандидату</h4>
                <div class="passport-field passport-html" style="margin-top: 5px;">${data.requirements}</div>
            </div>
        `;
    }
    
    // Функционал
    if (data.functionality) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-briefcase"></i> Функционал</h4>
                <div class="passport-field passport-html" style="margin-top: 5px;">${data.functionality}</div>
            </div>
        `;
    }
    
    // Условия работы
    if (data.free_meals || data.free_accommodation || data.salary_payment || data.local_work || data.part_time || data.deductions) {
        html += `<div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
            <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-utensils"></i> Условия работы</h4>`;
        if (data.free_meals) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>🍽️ Питание:</strong> ${escapeHtml(data.free_meals)}</div>`;
        if (data.free_accommodation) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>🏢 Проживание:</strong> ${escapeHtml(data.free_accommodation)}</div>`;
        if (data.salary_payment) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>💰 Выплата ЗП:</strong><br><div style="margin-top: 5px;">${escapeHtml(data.salary_payment)}</div></div>`;
        if (data.local_work) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>👥 Местные:</strong> ${escapeHtml(data.local_work)}</div>`;
        if (data.part_time) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>⏰ Подработка:</strong> ${escapeHtml(data.part_time)}</div>`;
        if (data.deductions) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>📉 Вычеты:</strong><br><div style="margin-top: 5px;">${escapeHtml(data.deductions)}</div></div>`;
        html += `</div>`;
    }
    
    // Особенности
    if (data.features) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-star"></i> Особенности</h4>
                <div class="passport-field passport-html" style="margin-top: 5px;">${data.features}</div>
            </div>
        `;
    }
    
    // График работы
    if (data.work_schedule) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-clock"></i> График работы</h4>
                <div class="passport-field" style="margin-top: 5px;">${escapeHtml(data.work_schedule)}</div>
            </div>
        `;
    }
    
    // Требуемые документы
    if (data.documents_required) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-file-alt"></i> Требуемые документы</h4>
                <div class="passport-field" style="margin-top: 5px;">${escapeHtml(data.documents_required)}</div>
            </div>
        `;
    }
    
    // Маршрутный лист
    if (data.route_sheet_filename) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-map"></i> Маршрутный лист</h4>
                <button class="btn-small" onclick="downloadRouteSheetFromView(${objectId})" style="background: #3498db;">
                    <i class="fas fa-download"></i> Скачать маршрутный лист (PDF)
                </button>
            </div>
        `;
    }
    
    if (html === '') {
        html = '<div style="text-align: center; padding: 40px; color: #999;">Паспорт объекта пока не заполнен</div>';
    }
    
    return html;
}

async function downloadRouteSheetFromView(objectId) {
    window.open(`/api/admin/objects/${objectId}/route-sheet/download`, '_blank');
}

function closePassportView() {
    const modal = document.getElementById('passportViewModal');
    if (modal) modal.remove();
}

// Делаем функции глобальными
window.viewPassport = viewPassport;
window.closePassportView = closePassportView;
window.downloadRouteSheetFromView = downloadRouteSheetFromView;