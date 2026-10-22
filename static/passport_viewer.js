// static/passport_viewer.js - просмотр паспорта для менеджеров с поддержкой нескольких маршрутных листов

// ========== ПРОСМОТР ПАСПОРТА ОБЪЕКТА ==========

async function viewPassport(objectId, objectName) {
    try {
        // Загружаем паспорт
        const passportResponse = await fetch(`/api/admin/objects/${objectId}/passport`, {
            credentials: 'include'
        });
        
        if (!passportResponse.ok) {
            showNotification('Ошибка загрузки паспорта', 'error');
            return;
        }
        
        const passportData = await passportResponse.json();
        
        // Загружаем маршрутные листы
        const sheetsResponse = await fetch(`/api/admin/objects/${objectId}/route-sheets`, {
            credentials: 'include'
        });
        
        let routeSheets = [];
        if (sheetsResponse.ok) {
            routeSheets = await sheetsResponse.json();
        }
        
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
                    ${renderPassportContent(passportData, routeSheets, objectId)}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('Ошибка загрузки паспорта', 'error');
    }
}

function renderPassportContent(passportData, routeSheets, objectId) {
    let html = '';
    
    // Адреса
    if (passportData.address_production || passportData.address_hostel) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-map-marker-alt"></i> Адреса</h4>
                ${passportData.address_production ? `<div class="passport-field" style="margin-bottom: 10px;"><strong>📍 Производство:</strong><br><div style="margin-top: 5px;">${escapeHtml(passportData.address_production)}</div></div>` : ''}
                ${passportData.address_hostel ? `<div class="passport-field" style="margin-bottom: 10px;"><strong>🏠 Хостел:</strong><br><div style="margin-top: 5px;">${escapeHtml(passportData.address_hostel)}</div></div>` : ''}
            </div>
        `;
    }
    
    // Операция/ставка (с HTML)
    if (passportData.operation_rate) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-chart-line"></i> Операция / Ставка</h4>
                <div class="passport-field passport-html" style="margin-top: 5px;">${passportData.operation_rate}</div>
            </div>
        `;
    }
    
    // Требования
    if (passportData.requirements) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-user-check"></i> Требования к кандидату</h4>
                <div class="passport-field passport-html" style="margin-top: 5px;">${passportData.requirements}</div>
            </div>
        `;
    }
    
    // Функционал
    if (passportData.functionality) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-briefcase"></i> Функционал</h4>
                <div class="passport-field passport-html" style="margin-top: 5px;">${passportData.functionality}</div>
            </div>
        `;
    }
    
    // Условия работы
    if (passportData.free_meals || passportData.free_accommodation || passportData.salary_payment || passportData.local_work || passportData.part_time || passportData.deductions) {
        html += `<div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
            <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-utensils"></i> Условия работы</h4>`;
        if (passportData.free_meals) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>🍽️ Питание:</strong> ${escapeHtml(passportData.free_meals)}</div>`;
        if (passportData.free_accommodation) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>🏢 Проживание:</strong> ${escapeHtml(passportData.free_accommodation)}</div>`;
        if (passportData.salary_payment) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>💰 Выплата ЗП:</strong><br><div style="margin-top: 5px;">${escapeHtml(passportData.salary_payment)}</div></div>`;
        if (passportData.local_work) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>👥 Местные:</strong> ${escapeHtml(passportData.local_work)}</div>`;
        if (passportData.part_time) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>⏰ Подработка:</strong> ${escapeHtml(passportData.part_time)}</div>`;
        if (passportData.deductions) html += `<div class="passport-field" style="margin-bottom: 8px;"><strong>📉 Вычеты:</strong><br><div style="margin-top: 5px;">${escapeHtml(passportData.deductions)}</div></div>`;
        html += `</div>`;
    }
    
    // Особенности
    if (passportData.features) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-star"></i> Особенности</h4>
                <div class="passport-field passport-html" style="margin-top: 5px;">${passportData.features}</div>
            </div>
        `;
    }
    
    // График работы
    if (passportData.work_schedule) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-clock"></i> График работы</h4>
                <div class="passport-field" style="margin-top: 5px;">${escapeHtml(passportData.work_schedule)}</div>
            </div>
        `;
    }
    
    // Требуемые документы
    if (passportData.documents_required) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-file-alt"></i> Требуемые документы</h4>
                <div class="passport-field" style="margin-top: 5px;">${escapeHtml(passportData.documents_required)}</div>
            </div>
        `;
    }
    
    // Маршрутные листы
    if (routeSheets && routeSheets.length > 0) {
        html += `
            <div class="passport-section" style="margin-bottom: 20px;">
                <h4 style="color: #A42C30; margin-bottom: 10px;"><i class="fas fa-map"></i> Маршрутные листы (${routeSheets.length})</h4>
                <div style="display: flex; flex-direction: column; gap: 8px;">
        `;
        
        for (const sheet of routeSheets) {
            const uploadDate = sheet.uploaded_at ? new Date(sheet.uploaded_at).toLocaleDateString('ru-RU') : '';
            html += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: #f8f9fa; border-radius: 8px; border-left: 3px solid #A42C30;">
                    <div style="display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0;">
                        <i class="fas fa-file-alt" style="color: #e74c3c; font-size: 18px;"></i>
                        <div style="flex: 1; min-width: 0;">
                            <div style="font-weight: 500; font-size: 0.9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(sheet.original_name)}">
                                ${escapeHtml(sheet.original_name)}
                            </div>
                            <div style="font-size: 0.7rem; color: var(--gray);">
                                ${uploadDate ? `📅 ${uploadDate}` : ''}
                            </div>
                        </div>
                    </div>
                    <button type="button" class="btn-small" onclick="downloadRouteSheetFromViewById(${sheet.id})" style="background: #3498db; padding: 4px 10px; font-size: 0.7rem;">
                        <i class="fas fa-download"></i> Скачать
                    </button>
                </div>
            `;
        }
        
        html += `
                </div>
            </div>
        `;
    }
    
    if (html === '') {
        html = '<div style="text-align: center; padding: 40px; color: #999;">Паспорт объекта пока не заполнен</div>';
    }
    
    return html;
}

function downloadRouteSheetFromViewById(sheetId) {
    // URL: /api/admin/objects/route-sheets/{sheet_id}/download
    window.open(`/api/admin/objects/route-sheets/${sheetId}/download`, '_blank');
}

function closePassportView() {
    const modal = document.getElementById('passportViewModal');
    if (modal) modal.remove();
}

// Вспомогательная функция для уведомлений (если нет глобальной)
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

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Делаем функции глобальными
window.viewPassport = viewPassport;
window.closePassportView = closePassportView;
window.downloadRouteSheetFromViewById = downloadRouteSheetFromViewById;
