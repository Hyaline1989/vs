// static/passport_editor.js - редактор паспорта для админ-панели с поддержкой нескольких маршрутных листов

// ========== УПРАВЛЕНИЕ ПАСПОРТОМ ОБЪЕКТА ==========
let currentPassportObjectId = null;
let routeSheetsList = [];

// Функция для показа уведомлений (если нет глобальной)
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

// Инициализация редактора паспорта
async function initPassportEditor(objectId) {
    currentPassportObjectId = objectId;
    
    // Загружаем существующий паспорт
    try {
        const response = await fetch(`/api/admin/objects/${objectId}/passport`, {
            credentials: 'include'
        });
        
        if (response.ok) {
            const data = await response.json();
            fillPassportForm(data);
        }
        
        // Загружаем список маршрутных листов
        await loadRouteSheets();
        
    } catch (error) {
        console.error('Ошибка загрузки паспорта:', error);
    }
}

function fillPassportForm(data) {
    // Обычные текстовые поля
    document.getElementById('passport_address_production').value = data.address_production || '';
    document.getElementById('passport_address_hostel').value = data.address_hostel || '';
    document.getElementById('passport_free_meals').value = data.free_meals || '';
    document.getElementById('passport_free_accommodation').value = data.free_accommodation || '';
    document.getElementById('passport_salary_payment').value = data.salary_payment || '';
    document.getElementById('passport_local_work').value = data.local_work || '';
    document.getElementById('passport_part_time').value = data.part_time || '';
    document.getElementById('passport_deductions').value = data.deductions || '';
    document.getElementById('passport_work_schedule').value = data.work_schedule || '';
    document.getElementById('passport_documents_required').value = data.documents_required || '';
    
    // Rich-text поля (если есть Quill)
    if (typeof Quill !== 'undefined') {
        if (window.operationRateEditor) {
            window.operationRateEditor.root.innerHTML = data.operation_rate || '';
        }
        if (window.requirementsEditor) {
            window.requirementsEditor.root.innerHTML = data.requirements || '';
        }
        if (window.functionalityEditor) {
            window.functionalityEditor.root.innerHTML = data.functionality || '';
        }
        if (window.featuresEditor) {
            window.featuresEditor.root.innerHTML = data.features || '';
        }
    } else {
        // fallback для textarea
        const opRate = document.getElementById('passport_operation_rate');
        if (opRate) opRate.value = data.operation_rate || '';
        const requirements = document.getElementById('passport_requirements');
        if (requirements) requirements.value = data.requirements || '';
        const functionality = document.getElementById('passport_functionality');
        if (functionality) functionality.value = data.functionality || '';
        const features = document.getElementById('passport_features');
        if (features) features.value = data.features || '';
    }
}

// ========== УПРАВЛЕНИЕ МАРШРУТНЫМИ ЛИСТАМИ ==========

async function loadRouteSheets() {
    if (!currentPassportObjectId) return;
    
    try {
        const response = await fetch(`/api/admin/objects/${currentPassportObjectId}/route-sheets`, {
            credentials: 'include'
        });
        
        if (response.ok) {
            routeSheetsList = await response.json();
            renderRouteSheetsList();
        } else {
            routeSheetsList = [];
            renderRouteSheetsList();
        }
    } catch (error) {
        console.error('Ошибка загрузки маршрутных листов:', error);
        routeSheetsList = [];
        renderRouteSheetsList();
    }
}

function renderRouteSheetsList() {
    const container = document.getElementById('routeSheetsContainer');
    if (!container) return;
    
    const maxFiles = 5;
    const currentCount = routeSheetsList.length;
    const canUpload = currentCount < maxFiles;
    
    let html = `
        <div style="margin-bottom: 10px;">
            <span style="color: var(--gray); font-size: 0.8rem;">
                <i class="fas fa-info-circle"></i> 
                Загружено: ${currentCount} из ${maxFiles} файлов
            </span>
        </div>
    `;
    
    if (routeSheetsList.length === 0) {
        html += `
            <div style="padding: 15px; background: #f8f9fa; border-radius: 8px; text-align: center; color: var(--gray);">
                <i class="fas fa-file-pdf" style="font-size: 24px; display: block; margin-bottom: 8px;"></i>
                Маршрутные листы не загружены
            </div>
        `;
    } else {
        html += `<div style="display: flex; flex-direction: column; gap: 8px;">`;
        
        for (const sheet of routeSheetsList) {
            const uploadDate = sheet.uploaded_at ? new Date(sheet.uploaded_at).toLocaleDateString('ru-RU') : '';
            const fileSize = sheet.file_size ? (sheet.file_size / 1024).toFixed(1) + ' KB' : '';
            
            html += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: #f8f9fa; border-radius: 8px; border-left: 3px solid var(--primary);">
                    <div style="display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0;">
                        <i class="fas fa-file-pdf" style="color: #e74c3c; font-size: 20px;"></i>
                        <div style="flex: 1; min-width: 0;">
                            <div style="font-weight: 500; font-size: 0.9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(sheet.original_name)}">
                                ${escapeHtml(sheet.original_name)}
                            </div>
                            <div style="font-size: 0.7rem; color: var(--gray);">
                                ${uploadDate ? `📅 ${uploadDate}` : ''}
                                ${fileSize ? ` • 📄 ${fileSize}` : ''}
                                ${sheet.uploaded_by ? ` • 👤 ID: ${sheet.uploaded_by}` : ''}
                            </div>
                        </div>
                    </div>
                    <div style="display: flex; gap: 6px; flex-shrink: 0;">
                        <button type="button" class="btn-small" onclick="downloadRouteSheetById(${sheet.id})" style="background: #3498db; padding: 4px 10px; font-size: 0.7rem;">
                            <i class="fas fa-download"></i>
                        </button>
                        <button type="button" class="btn-small" onclick="deleteRouteSheetById(${sheet.id})" style="background: #e74c3c; padding: 4px 10px; font-size: 0.7rem;">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
        }
        
        html += `</div>`;
    }
    
    // Кнопка загрузки нового файла
    if (canUpload) {
        html += `
            <div style="margin-top: 12px;">
                <input type="file" id="routeSheetInput" accept=".pdf" style="display: none;" onchange="uploadRouteSheet(this)">
                <button type="button" class="btn-small" onclick="document.getElementById('routeSheetInput').click()" style="background: #27ae60; padding: 8px 16px;">
                    <i class="fas fa-upload"></i> Загрузить PDF (${currentCount}/${maxFiles})
                </button>
                <span style="font-size: 0.7rem; color: var(--gray); margin-left: 10px;">
                    Только PDF, максимум 30 MB
                </span>
            </div>
        `;
    } else {
        html += `
            <div style="margin-top: 12px; padding: 8px 12px; background: #fff3cd; border-radius: 6px; font-size: 0.8rem; color: #856404;">
                <i class="fas fa-exclamation-triangle"></i> 
                Достигнут лимит (${maxFiles} файлов). Удалите один из файлов, чтобы загрузить новый.
            </div>
        `;
    }
    
    container.innerHTML = html;
}

async function uploadRouteSheet(input) {
    if (!input.files || input.files.length === 0) return;
    
    const file = input.files[0];
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showNotification('❌ Можно загружать только PDF файлы', 'error');
        return;
    }
    
    // Проверка размера файла (30 MB)
    const maxSize = 30 * 1024 * 1024; // 30 MB
    if (file.size > maxSize) {
        showNotification(`❌ Файл слишком большой. Максимум 30 MB`, 'error');
        return;
    }
    
    // Проверка количества файлов
    if (routeSheetsList.length >= 5) {
        showNotification('❌ Достигнут лимит 5 файлов', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('route_sheet', file);
    
    // Показываем индикатор загрузки
    const uploadBtn = document.querySelector('#routeSheetsContainer .btn-small');
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';
    }
    
    try {
        const response = await fetch(`/api/admin/objects/${currentPassportObjectId}/route-sheets`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            showNotification(`✅ Файл "${file.name}" загружен`, 'success');
            await loadRouteSheets();
        } else {
            showNotification(`❌ ${result.error || 'Ошибка загрузки'}`, 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('❌ Ошибка загрузки', 'error');
    } finally {
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="fas fa-upload"></i> Загрузить PDF';
        }
    }
    
    input.value = '';
}

async function deleteRouteSheetById(sheetId) {
    if (!confirm('Удалить этот маршрутный лист?')) return;
    
    try {
        const response = await fetch(`/api/admin/objects/route-sheets/${sheetId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (response.ok) {
            showNotification('✅ Маршрутный лист удалён', 'success');
            await loadRouteSheets();
        } else {
            const error = await response.json();
            showNotification(`❌ ${error.error || 'Ошибка удаления'}`, 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('❌ Ошибка удаления', 'error');
    }
}

function downloadRouteSheetById(sheetId) {
    // URL: /api/admin/objects/route-sheets/{sheet_id}/download
    window.open(`/api/admin/objects/route-sheets/${sheetId}/download`, '_blank');
}

// ========== СОХРАНЕНИЕ ПАСПОРТА ==========

async function savePassport() {
    // Собираем данные из обычных полей
    const passportData = {
        address_production: document.getElementById('passport_address_production').value,
        address_hostel: document.getElementById('passport_address_hostel').value,
        free_meals: document.getElementById('passport_free_meals').value,
        free_accommodation: document.getElementById('passport_free_accommodation').value,
        salary_payment: document.getElementById('passport_salary_payment').value,
        local_work: document.getElementById('passport_local_work').value,
        part_time: document.getElementById('passport_part_time').value,
        deductions: document.getElementById('passport_deductions').value,
        work_schedule: document.getElementById('passport_work_schedule').value,
        documents_required: document.getElementById('passport_documents_required').value
    };
    
    // Rich-text поля
    if (typeof Quill !== 'undefined') {
        passportData.operation_rate = window.operationRateEditor ? window.operationRateEditor.root.innerHTML : '';
        passportData.requirements = window.requirementsEditor ? window.requirementsEditor.root.innerHTML : '';
        passportData.functionality = window.functionalityEditor ? window.functionalityEditor.root.innerHTML : '';
        passportData.features = window.featuresEditor ? window.featuresEditor.root.innerHTML : '';
    } else {
        passportData.operation_rate = document.getElementById('passport_operation_rate')?.value || '';
        passportData.requirements = document.getElementById('passport_requirements')?.value || '';
        passportData.functionality = document.getElementById('passport_functionality')?.value || '';
        passportData.features = document.getElementById('passport_features')?.value || '';
    }
    
    try {
        const response = await fetch(`/api/admin/objects/${currentPassportObjectId}/passport`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(passportData)
        });
        
        if (response.ok) {
            showNotification('✅ Паспорт объекта сохранён', 'success');
        } else {
            const error = await response.json();
            showNotification('❌ ' + (error.error || 'Ошибка сохранения'), 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('❌ Ошибка сохранения', 'error');
    }
}

// ========== ОТКРЫТИЕ И ЗАКРЫТИЕ РЕДАКТОРА ==========

function openPassportEditor(objectId, objectName) {
    currentPassportObjectId = objectId;
    
    // Создаём модальное окно для редактирования паспорта
    let modal = document.getElementById('passportEditorModal');
    if (modal) modal.remove();
    
    modal = document.createElement('div');
    modal.id = 'passportEditorModal';
    modal.className = 'modal passport-modal';
    modal.style.display = 'flex';
    
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 950px; width: 95%; max-height: 90vh;">
            <div class="modal-header" style="background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);">
                <h3><i class="fas fa-id-card"></i> Паспорт объекта: ${escapeHtml(objectName)}</h3>
                <button class="modal-close" onclick="closePassportEditor()">&times;</button>
            </div>
            <div class="modal-body" style="max-height: calc(90vh - 70px); overflow-y: auto; padding: 20px;">
                <form id="passportForm" onsubmit="event.preventDefault(); savePassport();">
                    <!-- Основная информация -->
                    <div class="form-section">
                        <h4><i class="fas fa-map-marker-alt"></i> Адреса</h4>
                        <div class="form-group">
                            <label>Адрес производства</label>
                            <textarea id="passport_address_production" rows="2" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;"></textarea>
                        </div>
                        <div class="form-group">
                            <label>Адрес хостела</label>
                            <textarea id="passport_address_hostel" rows="2" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;"></textarea>
                        </div>
                    </div>
                    
                    <!-- Rich-text поля -->
                    <div class="form-section">
                        <h4><i class="fas fa-chart-line"></i> Операция / Ставка</h4>
                        <div id="operation_rate_editor" style="height: 150px; margin-bottom: 10px;"></div>
                        <textarea id="passport_operation_rate" style="display: none;"></textarea>
                    </div>
                    
                    <div class="form-section">
                        <h4><i class="fas fa-user-check"></i> Требования к кандидату</h4>
                        <div id="requirements_editor" style="height: 150px; margin-bottom: 10px;"></div>
                        <textarea id="passport_requirements" style="display: none;"></textarea>
                    </div>
                    
                    <div class="form-section">
                        <h4><i class="fas fa-briefcase"></i> Функционал</h4>
                        <div id="functionality_editor" style="height: 150px; margin-bottom: 10px;"></div>
                        <textarea id="passport_functionality" style="display: none;"></textarea>
                    </div>
                    
                    <!-- Условия работы -->
                    <div class="form-section">
                        <h4><i class="fas fa-utensils"></i> Условия работы</h4>
                        <div class="form-row" style="display: flex; gap: 15px; flex-wrap: wrap;">
                            <div class="form-group" style="flex: 1;">
                                <label>Бесплатное питание</label>
                                <input type="text" id="passport_free_meals" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;">
                            </div>
                            <div class="form-group" style="flex: 1;">
                                <label>Бесплатное проживание</label>
                                <input type="text" id="passport_free_accommodation" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;">
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Выплата ЗП</label>
                            <textarea id="passport_salary_payment" rows="3" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;"></textarea>
                        </div>
                        <div class="form-row" style="display: flex; gap: 15px; flex-wrap: wrap;">
                            <div class="form-group" style="flex: 1;">
                                <label>Местные</label>
                                <input type="text" id="passport_local_work" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;">
                            </div>
                            <div class="form-group" style="flex: 1;">
                                <label>Подработка</label>
                                <input type="text" id="passport_part_time" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;">
                            </div>
                        </div>
                        <div class="form-group">
                            <label>Вычеты</label>
                            <textarea id="passport_deductions" rows="2" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;"></textarea>
                        </div>
                    </div>
                    
                    <!-- Особенности -->
                    <div class="form-section">
                        <h4><i class="fas fa-star"></i> Особенности</h4>
                        <div id="features_editor" style="height: 150px; margin-bottom: 10px;"></div>
                        <textarea id="passport_features" style="display: none;"></textarea>
                    </div>
                    
                    <div class="form-section">
                        <h4><i class="fas fa-clock"></i> График работы</h4>
                        <textarea id="passport_work_schedule" rows="3" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;"></textarea>
                    </div>
                    
                    <div class="form-section">
                        <h4><i class="fas fa-file-alt"></i> Требуемые документы</h4>
                        <textarea id="passport_documents_required" rows="3" class="form-control" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;"></textarea>
                    </div>
                    
                    <!-- Маршрутные листы -->
                    <div class="form-section">
                        <h4><i class="fas fa-map"></i> Маршрутные листы (PDF, максимум 5)</h4>
                        <div id="routeSheetsContainer"></div>
                    </div>
                    
                    <div class="form-actions" style="display: flex; justify-content: flex-end; gap: 15px; margin-top: 25px; padding-top: 20px; border-top: 1px solid #eee;">
                        <button type="button" class="btn-cancel" onclick="closePassportEditor()">Отмена</button>
                        <button type="submit" class="btn-save">Сохранить паспорт</button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Инициализируем Quill редакторы, если библиотека загружена
    if (typeof Quill !== 'undefined') {
        const toolbarOptions = [
            ['bold', 'italic', 'underline'],
            [{ 'list': 'ordered'}, { 'list': 'bullet' }],
            ['clean']
        ];
        
        window.operationRateEditor = new Quill('#operation_rate_editor', {
            theme: 'snow',
            placeholder: 'Введите информацию об операции и ставке...',
            modules: { toolbar: toolbarOptions }
        });
        
        window.requirementsEditor = new Quill('#requirements_editor', {
            theme: 'snow',
            placeholder: 'Введите требования к кандидатам...',
            modules: { toolbar: toolbarOptions }
        });
        
        window.functionalityEditor = new Quill('#functionality_editor', {
            theme: 'snow',
            placeholder: 'Опишите функционал...',
            modules: { toolbar: toolbarOptions }
        });
        
        window.featuresEditor = new Quill('#features_editor', {
            theme: 'snow',
            placeholder: 'Особенности работы...',
            modules: { toolbar: toolbarOptions }
        });
    }
    
    // Загружаем данные
    initPassportEditor(objectId);
}

function closePassportEditor() {
    const modal = document.getElementById('passportEditorModal');
    if (modal) modal.remove();
}

// Делаем функции глобальными
window.openPassportEditor = openPassportEditor;
window.closePassportEditor = closePassportEditor;
window.savePassport = savePassport;
window.uploadRouteSheet = uploadRouteSheet;
window.deleteRouteSheetById = deleteRouteSheetById;
window.downloadRouteSheetById = downloadRouteSheetById;
window.loadRouteSheets = loadRouteSheets;