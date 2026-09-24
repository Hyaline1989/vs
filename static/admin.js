// static/admin.js - полная версия с мобильной адаптацией, правами для руководителя и имперсонацией

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

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU');
}

function formatDateTime(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU');
}

function getTodayDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
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

// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
let usersList = [];
let currentEditUserId = null;
let isLoadingUsers = false;
let userLoadRetryCount = 0;
const MAX_RETRIES = 3;
const RETRY_DELAY = 2000;

// ========== ЗАГРУЗКА ПОЛЬЗОВАТЕЛЕЙ ==========
async function loadUsers(retry = true) {
    if (isLoadingUsers) {
        console.log('Загрузка пользователей уже выполняется');
        return;
    }
    
    isLoadingUsers = true;
    
    try {
        const response = await fetch('/api/admin/users', { credentials: 'include' });
        
        if (response.status === 429) {
            console.warn('Слишком много запросов к API пользователей');
            const container = document.getElementById('usersTableContainer');
            if (container) {
                container.innerHTML = `
                    <div class="error-state">
                        <i class="fas fa-clock"></i>
                        <p>Слишком много запросов. Подождите немного...</p>
                        <button onclick="loadUsers()" class="retry-btn">Повторить</button>
                    </div>
                `;
            }
            
            if (retry && userLoadRetryCount < MAX_RETRIES) {
                userLoadRetryCount++;
                setTimeout(() => {
                    isLoadingUsers = false;
                    loadUsers(retry);
                }, RETRY_DELAY);
            }
            return;
        }
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Ошибка загрузки пользователей:', response.status, errorText);
            throw new Error(`HTTP ${response.status}`);
        }
        
        const users = await response.json();
        userLoadRetryCount = 0;
        
        if (Array.isArray(users)) {
            usersList = users;
            renderUsersTable(users);
        } else {
            console.error('Неверный формат ответа:', users);
            renderErrorState('Неверный формат данных от сервера');
        }
    } catch (error) {
        console.error('Ошибка загрузки пользователей:', error);
        renderErrorState('Не удалось загрузить список пользователей');
        
        if (retry && userLoadRetryCount < MAX_RETRIES) {
            userLoadRetryCount++;
            setTimeout(() => {
                isLoadingUsers = false;
                loadUsers(retry);
            }, RETRY_DELAY);
        }
    } finally {
        isLoadingUsers = false;
    }
}

function renderErrorState(message) {
    const container = document.getElementById('usersTableContainer');
    if (container) {
        container.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>${escapeHtml(message)}</p>
                <button onclick="loadUsers()" class="retry-btn">Повторить</button>
            </div>
        `;
    }
}

function renderUsersTable(users) {
    const container = document.getElementById('usersTableContainer');
    if (!container) return;
    
    if (!users || users.length === 0) {
        container.innerHTML = '<div class="empty-state">Нет пользователей</div>';
        return;
    }
    
    const isSystemAdmin = window.currentUser?.is_system_admin === true;
    const isAdmin = window.currentUser?.role === 'admin';
    const isManager = window.currentUser?.role === 'manager';
    const isMobile = window.innerWidth <= 768;
    
    // На мобильных используем карточки вместо таблицы
    if (isMobile) {
        let html = '<div class="users-cards">';
        
        for (const user of users) {
            if (isManager && user.role !== 'viewer') continue;
            
            const roleClass = user.role === 'admin' ? 'role-admin' : (user.role === 'manager' ? 'role-manager' : 'role-viewer');
            let roleName = user.role === 'admin' ? 'Администратор' : (user.role === 'manager' ? 'Руководитель' : 'Менеджер');
            
            if (user.id === 1) {
                roleName = 'Системный администратор';
            }
            
            const statusClass = user.is_active ? 'status-active' : 'status-inactive';
            const statusText = user.is_active ? 'Активен' : 'Заблокирован';
            
            let canEdit = false;
            let canDelete = false;
            let canManagePermissions = false;
            
            if (isSystemAdmin) {
                canEdit = true;
                canDelete = user.id !== window.currentUser?.id;
                canManagePermissions = true;
            }
            else if (isAdmin) {
                if (user.id !== 1 && user.role !== 'admin') {
                    canEdit = true;
                    canDelete = true;
                    canManagePermissions = true;
                }
            }
            else if (isManager && user.role === 'viewer') {
                canEdit = true;
                canDelete = true;
                canManagePermissions = true;
            }
            
            html += `
                <div class="user-card" data-user-id="${user.id}">
                    <div class="user-card-header">
                        <div class="user-card-name">
                            <strong>${escapeHtml(user.username)}</strong>
                            <span class="role-badge ${roleClass}">${roleName}</span>
                        </div>
                        <div class="user-card-status">
                            <span class="status-badge ${statusClass}">${statusText}</span>
                        </div>
                    </div>
                    <div class="user-card-info">
                        <div><i class="fas fa-user"></i> ${escapeHtml(user.full_name || '-')}</div>
                        <div><i class="fas fa-envelope"></i> ${escapeHtml(user.email || '-')}</div>
                        <div><i class="fas fa-calendar"></i> Создан: ${formatDate(user.created_at)}</div>
                        <div><i class="fas fa-clock"></i> Последний вход: ${user.last_login ? formatDateTime(user.last_login) : 'Никогда'}</div>
                    </div>
                    <div class="user-card-actions">
            `;
            
            if (canEdit) {
                html += `<button class="action-btn edit-btn" onclick="editUser(${user.id})" title="Редактировать"><i class="fas fa-edit"></i> Редактировать</button>`;
            }
            
            if (canDelete && user.id !== window.currentUser?.id) {
                html += `<button class="action-btn delete-btn" onclick="deleteUser(${user.id})" title="Удалить"><i class="fas fa-trash"></i> Удалить</button>`;
            }
            
            if (canManagePermissions) {
                html += `<button class="action-btn perms-btn" onclick="editPermissions(${user.id})" title="Права доступа"><i class="fas fa-lock"></i> Права</button>`;
            }
            
            // Кнопка "Войти как" - только для системного администратора
            if (isSystemAdmin && user.id !== window.currentUser?.id) {
                html += `<button class="action-btn impersonate-btn" onclick="impersonateUser(${user.id})" title="Войти как пользователь">
                    <i class="fas fa-user-astronaut"></i> Войти как
                </button>`;
            }
            
            html += `</div></div>`;
        }
        
        html += '</div>';
        container.innerHTML = html;
        return;
    }
    
    // На десктопе используем таблицу
    let html = `
        <table class="users-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Имя пользователя</th>
                    <th>Полное имя</th>
                    <th>Email</th>
                    <th>Роль</th>
                    <th>Статус</th>
                    <th>Создан</th>
                    <th>Последний вход</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    for (const user of users) {
        if (isManager && user.role !== 'viewer') continue;
        
        const roleClass = user.role === 'admin' ? 'role-admin' : (user.role === 'manager' ? 'role-manager' : 'role-viewer');
        let roleName = user.role === 'admin' ? 'Администратор' : (user.role === 'manager' ? 'Руководитель' : 'Менеджер');
        
        if (user.id === 1) {
            roleName = 'Системный администратор';
        }
        
        const statusClass = user.is_active ? 'status-active' : 'status-inactive';
        const statusText = user.is_active ? 'Активен' : 'Заблокирован';
        
        let canEdit = false;
        let canDelete = false;
        let canManagePermissions = false;
        
        if (isSystemAdmin) {
            canEdit = true;
            canDelete = user.id !== window.currentUser?.id;
            canManagePermissions = true;
        }
        else if (isAdmin) {
            if (user.id !== 1 && user.role !== 'admin') {
                canEdit = true;
                canDelete = true;
                canManagePermissions = true;
            }
        }
        else if (isManager && user.role === 'viewer') {
            canEdit = true;
            canDelete = true;
            canManagePermissions = true;
        }
        
        html += `
            <tr data-user-id="${user.id}">
                <td>${user.id}</td>
                <td><strong>${escapeHtml(user.username)}</strong></td>
                <td>${escapeHtml(user.full_name || '-')}</td>
                <td>${escapeHtml(user.email || '-')}</td>
                <td><span class="role-badge ${roleClass}">${roleName}</span></td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                <td>${formatDate(user.created_at)}</td>
                <td>${user.last_login ? formatDateTime(user.last_login) : 'Никогда'}</td>
                <td class="actions-cell">
        `;
        
        if (canEdit) {
            html += `<button class="action-btn edit-btn" onclick="editUser(${user.id})" title="Редактировать"><i class="fas fa-edit"></i></button>`;
        }
        
        if (canDelete && user.id !== window.currentUser?.id) {
            html += `<button class="action-btn delete-btn" onclick="deleteUser(${user.id})" title="Удалить"><i class="fas fa-trash"></i></button>`;
        }
        
        if (canManagePermissions) {
            html += `<button class="action-btn perms-btn" onclick="editPermissions(${user.id})" title="Права доступа"><i class="fas fa-lock"></i></button>`;
        }
        
        // Кнопка "Войти как" - только для системного администратора
        if (isSystemAdmin && user.id !== window.currentUser?.id) {
            html += `<button class="action-btn impersonate-btn" onclick="impersonateUser(${user.id})" title="Войти как пользователь"><i class="fas fa-user-astronaut"></i></button>`;
        }
        
        html += `</td></tr>`;
    }
    
    html += `</tbody></table>`;
    container.innerHTML = html;
}

// ========== РЕДАКТИРОВАНИЕ ПОЛЬЗОВАТЕЛЯ ==========
function editUser(userId) {
    const user = usersList.find(u => u.id === userId);
    if (!user) return;
    
    currentEditUserId = userId;
    document.getElementById('modalTitle').textContent = 'Редактировать пользователя';
    document.getElementById('userId').value = userId;
    document.getElementById('username').value = user.username;
    document.getElementById('username').disabled = true;
    document.getElementById('fullName').value = user.full_name || '';
    document.getElementById('email').value = user.email || '';
    document.getElementById('userRole').value = user.role;
    document.getElementById('isActive').checked = user.is_active;
    document.getElementById('password').value = '';
    document.getElementById('confirmPassword').value = '';
    document.getElementById('passwordField').style.display = 'block';
    document.getElementById('confirmPasswordField').style.display = 'block';
    
    document.getElementById('userModal').style.display = 'flex';
}

// ========== ДОБАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯ ==========
function openAddUserModal() {
    currentEditUserId = null;
    document.getElementById('modalTitle').textContent = 'Добавить пользователя';
    document.getElementById('userForm').reset();
    document.getElementById('userId').value = '';
    document.getElementById('username').disabled = false;
    document.getElementById('passwordField').style.display = 'block';
    document.getElementById('confirmPasswordField').style.display = 'block';
    document.getElementById('userModal').style.display = 'flex';
}

// ========== СОХРАНЕНИЕ ПОЛЬЗОВАТЕЛЯ ==========
async function saveUser() {
    const userId = document.getElementById('userId').value;
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const fullName = document.getElementById('fullName').value;
    const email = document.getElementById('email').value;
    const role = document.getElementById('userRole').value;
    const isActive = document.getElementById('isActive').checked;
    
    if (password !== confirmPassword) {
        showNotification('❌ Пароли не совпадают', 'error');
        return;
    }
    
    if (!userId && password.length < 4) {
        showNotification('❌ Пароль должен быть не менее 4 символов', 'error');
        return;
    }
    
    try {
        let url, method, body;
        if (userId) {
            url = `/api/admin/users/${userId}`;
            method = 'PUT';
            body = { full_name: fullName, email: email, is_active: isActive };
            if (password) body.password = password;
        } else {
            url = '/api/admin/users';
            method = 'POST';
            body = { username, password, full_name: fullName, email: email, role };
        }
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(body)
        });
        
        if (response.ok) {
            showNotification('✅ Сохранено', 'success');
            closeUserModal();
            loadUsers();
        } else {
            const error = await response.json();
            showNotification('❌ ' + (error.error || 'Ошибка'), 'error');
        }
    } catch (error) {
        showNotification('❌ Ошибка сохранения', 'error');
    }
}

// ========== УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ ==========
async function deleteUser(userId) {
    if (!confirm('Вы уверены, что хотите удалить этого пользователя?')) return;
    
    try {
        const response = await fetch(`/api/admin/users/${userId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (response.ok) {
            showNotification('✅ Пользователь удалён', 'success');
            loadUsers();
        } else {
            showNotification('❌ Ошибка удаления', 'error');
        }
    } catch (error) {
        showNotification('❌ Ошибка удаления', 'error');
    }
}

// ========== РЕДАКТИРОВАНИЕ ПРАВ ==========
async function editPermissions(userId) {
    // Проверка: manager может управлять только viewer
    if (window.currentUser?.role === 'manager') {
        const targetUser = usersList.find(u => u.id === userId);
        if (targetUser && targetUser.role !== 'viewer') {
            showNotification('Руководитель может управлять правами только менеджеров', 'error');
            return;
        }
    }
    
    try {
        const moduleRes = await fetch(`/api/admin/permissions/modules/${userId}`, { credentials: 'include' });
        const objectsDataRes = await fetch(`/api/selection/settings?for_permissions=true`, { credentials: 'include' });
        const objectPermsRes = await fetch(`/api/admin/permissions/objects/${userId}`, { credentials: 'include' });
        
        if (!moduleRes.ok) {
            if (moduleRes.status === 403) {
                showNotification('У вас нет прав для просмотра прав этого пользователя', 'error');
            } else if (moduleRes.status === 401) {
                showNotification('Сессия истекла, войдите заново', 'error');
                setTimeout(() => { window.location.href = '/'; }, 1500);
            } else {
                showNotification('Ошибка загрузки прав', 'error');
            }
            return;
        }
        
        if (!objectsDataRes.ok) {
            if (objectsDataRes.status === 403) {
                showNotification('У вас нет доступа к списку объектов', 'error');
            } else if (objectsDataRes.status === 401) {
                showNotification('Сессия истекла, войдите заново', 'error');
                setTimeout(() => { window.location.href = '/'; }, 1500);
            } else {
                showNotification('Ошибка загрузки объектов', 'error');
            }
            return;
        }
        
        if (!objectPermsRes.ok) {
            if (objectPermsRes.status === 403) {
                showNotification('У вас нет прав для просмотра прав на объекты', 'error');
            } else if (objectPermsRes.status === 401) {
                showNotification('Сессия истекла, войдите заново', 'error');
                setTimeout(() => { window.location.href = '/'; }, 1500);
            } else {
                showNotification('Ошибка загрузки прав на объекты', 'error');
            }
            return;
        }
        
        const modulePerms = await moduleRes.json();
        const objectsData = await objectsDataRes.json();
        const objectPerms = await objectPermsRes.json();
        
        console.log('Загруженные права на модули:', modulePerms);
        
        // Получаем модули, доступные текущему пользователю (для manager)
        let availableModules = ['dashboard', 'selection', 'worker_status', 'reports'];
        let moduleLabels = {
            'dashboard': '📊 Дашборд План/Факт',
            'selection': '🎯 Подбор объектов',
            'worker_status': '👥 Вахтовики',
            'reports': '📋 Отчёты'
        };
        
        if (window.currentUser?.role === 'manager') {
            try {
                const myModulesRes = await fetch(`/api/admin/permissions/modules/${window.currentUser.id}`, { credentials: 'include' });
                if (myModulesRes.ok) {
                    const myModules = await myModulesRes.json();
                    availableModules = availableModules.filter(module => myModules[module] === true);
                }
            } catch(e) {
                console.error('Ошибка получения прав текущего пользователя на модули:', e);
            }
        }
        
        // Получаем объекты, доступные текущему пользователю (для manager)
        let availableObjects = objectsData.objects || [];
        if (window.currentUser?.role === 'manager') {
            try {
                const myPermsRes = await fetch(`/api/admin/permissions/objects/${window.currentUser.id}`, { credentials: 'include' });
                if (myPermsRes.ok) {
                    const myPerms = await myPermsRes.json();
                    const visibleObjectIds = Object.keys(myPerms).filter(objId => myPerms[objId]?.selection === true).map(Number);
                    availableObjects = availableObjects.filter(obj => visibleObjectIds.includes(obj.id));
                }
            } catch(e) {
                console.error('Ошибка получения прав текущего пользователя:', e);
            }
        }
        
        let html = `
            <div class="permissions-section">
                <h4>📱 Доступ к модулям</h4>
                <div class="modules-perms">
        `;
        
        for (const module of availableModules) {
            const isChecked = modulePerms[module] === true;
            html += `
                <label class="perm-checkbox">
                    <input type="checkbox" id="perm_${module}" ${isChecked ? 'checked' : ''}>
                    <span>${moduleLabels[module]}</span>
                </label>
            `;
        }
        
        html += `
                </div>
            </div>
            <div class="permissions-section">
                <h4>🏢 Доступ к объектам (только для Подбора объектов)</h4>
                <div class="objects-perms-header">
                    <button type="button" class="btn-small" onclick="selectAllObjects()">Выбрать все</button>
                    <button type="button" class="btn-small" onclick="deselectAllObjects()">Снять все</button>
                </div>
                <div class="objects-perms-list" id="objectsPermsList">
        `;
        
        for (const obj of availableObjects) {
            const perms = objectPerms[obj.id] || { selection: false };
            html += `
                <div class="object-perm-item" data-object-id="${obj.id}">
                    <div class="object-perm-name">${escapeHtml(obj.name)}</div>
                    <div class="object-perm-checkboxes">
                        <label class="perm-checkbox-small">
                            <input type="checkbox" class="obj-select-perm" data-obj="${obj.id}" ${perms.selection ? 'checked' : ''}>
                            <span>🎯 Подбор объектов</span>
                        </label>
                    </div>
                </div>
            `;
        }
        
        html += `</div></div>`;
        document.getElementById('permissionsContainer').innerHTML = html;
        document.getElementById('permissionsModal').style.display = 'flex';
        window.currentPermsUserId = userId;
    } catch (error) {
        console.error('Ошибка в editPermissions:', error);
        showNotification('❌ Ошибка загрузки прав', 'error');
    }
}

// ========== СОХРАНЕНИЕ ПРАВ ==========
async function savePermissions() {
    const userId = window.currentPermsUserId;
    
    const modulePerms = {};
    const permDashboard = document.getElementById('perm_dashboard');
    const permSelection = document.getElementById('perm_selection');
    const permWorkerStatus = document.getElementById('perm_worker_status');
    const permReports = document.getElementById('perm_reports');
    
    if (permDashboard) modulePerms.dashboard = permDashboard.checked;
    if (permSelection) modulePerms.selection = permSelection.checked;
    if (permWorkerStatus) modulePerms.worker_status = permWorkerStatus.checked;
    if (permReports) modulePerms.reports = permReports.checked;
    
    console.log('Сохраняемые права на модули:', modulePerms);
    
    const objectPerms = {};
    document.querySelectorAll('.object-perm-item').forEach(item => {
        const objId = parseInt(item.dataset.objectId);
        objectPerms[objId] = {
            selection: item.querySelector('.obj-select-perm')?.checked || false
        };
    });
    
    try {
        const promises = [];
        
        if (Object.keys(modulePerms).length > 0) {
            promises.push(
                fetch(`/api/admin/permissions/modules/${userId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(modulePerms)
                })
            );
        }
        
        promises.push(
            fetch(`/api/admin/permissions/objects/${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(objectPerms)
            })
        );
        
        const results = await Promise.all(promises);
        let allOk = true;
        
        for (const res of results) {
            if (!res.ok) {
                allOk = false;
                const error = await res.json();
                console.error('Ошибка сохранения:', error);
            }
        }
        
        if (allOk) {
            showNotification('✅ Права сохранены', 'success');
            closePermissionsModal();
        } else {
            showNotification('❌ Ошибка сохранения прав', 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('❌ Ошибка сохранения прав', 'error');
    }
}

// ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
function selectAllObjects() {
    document.querySelectorAll('.obj-select-perm').forEach(cb => cb.checked = true);
}

function deselectAllObjects() {
    document.querySelectorAll('.obj-select-perm').forEach(cb => cb.checked = false);
}

function closeUserModal() {
    document.getElementById('userModal').style.display = 'none';
    document.getElementById('username').disabled = false;
}

function closePermissionsModal() {
    document.getElementById('permissionsModal').style.display = 'none';
}

function filterUsers() {
    const searchTerm = document.getElementById('searchUsers').value.toLowerCase();
    const roleFilter = document.getElementById('filterRole').value;
    const statusFilter = document.getElementById('filterStatus').value;
    
    const container = document.getElementById('usersTableContainer');
    if (!container) return;
    
    const isMobile = window.innerWidth <= 768;
    
    if (isMobile) {
        const cards = document.querySelectorAll('.user-card');
        cards.forEach(card => {
            const username = card.querySelector('.user-card-name strong')?.textContent.toLowerCase() || '';
            const fullName = card.querySelector('.user-card-info div:first-child')?.textContent.replace('👤', '').trim().toLowerCase() || '';
            const roleBadge = card.querySelector('.role-badge')?.textContent.toLowerCase() || '';
            const statusBadge = card.querySelector('.status-badge')?.textContent.toLowerCase() || '';
            
            let matches = true;
            
            if (searchTerm && !username.includes(searchTerm) && !fullName.includes(searchTerm)) {
                matches = false;
            }
            
            if (roleFilter !== 'all') {
                const roleMap = { 'admin': 'администратор', 'manager': 'руководитель', 'viewer': 'менеджер' };
                if (!roleBadge.includes(roleMap[roleFilter])) matches = false;
            }
            
            if (statusFilter !== 'all') {
                const statusActive = statusBadge === 'активен';
                if (statusFilter === 'active' && !statusActive) matches = false;
                if (statusFilter === 'inactive' && statusActive) matches = false;
            }
            
            card.style.display = matches ? '' : 'none';
        });
    } else {
        const rows = document.querySelectorAll('#usersTableContainer tbody tr');
        rows.forEach(row => {
            const username = row.cells[1]?.textContent.toLowerCase() || '';
            const fullName = row.cells[2]?.textContent.toLowerCase() || '';
            const role = row.cells[4]?.textContent.toLowerCase() || '';
            const status = row.cells[5]?.textContent.toLowerCase() || '';
            
            let matches = true;
            
            if (searchTerm && !username.includes(searchTerm) && !fullName.includes(searchTerm)) {
                matches = false;
            }
            
            if (roleFilter !== 'all') {
                const roleMap = { 'admin': 'администратор', 'manager': 'руководитель', 'viewer': 'менеджер' };
                if (!role.includes(roleMap[roleFilter])) matches = false;
            }
            
            if (statusFilter !== 'all') {
                const statusActive = status === 'активен';
                if (statusFilter === 'active' && !statusActive) matches = false;
                if (statusFilter === 'inactive' && statusActive) matches = false;
            }
            
            row.style.display = matches ? '' : 'none';
        });
    }
}

// ========== ГЕНЕРАЦИЯ СНАПШОТОВ ==========
async function generateSnapshots() {
    const fromDate = prompt('Введите начальную дату (ГГГГ-ММ-ДД):', getTodayDate());
    if (!fromDate) return;
    
    const toDate = prompt('Введите конечную дату (ГГГГ-ММ-ДД):', fromDate);
    if (!toDate) return;
    
    showNotification('🔄 Генерация снапшотов...', 'info');
    
    try {
        const response = await fetch('/api/snapshot/generate-range', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ from: fromDate, to: toDate })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`✅ Сгенерировано ${data.success_count} снапшотов из ${data.total}`, 'success');
        } else {
            showNotification('❌ Ошибка генерации', 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('❌ Ошибка генерации', 'error');
    }
}

// ========== ИМПЕРСОНАЦИЯ (ВХОД КАК ПОЛЬЗОВАТЕЛЬ) ==========

async function impersonateUser(userId) {
    if (!window.currentUser?.is_system_admin) {
        showNotification('❌ Только системный администратор может входить как другой пользователь', 'error');
        return;
    }
    
    // Получаем информацию о пользователе
    const user = usersList.find(u => u.id === userId);
    if (!user) {
        showNotification('❌ Пользователь не найден', 'error');
        return;
    }
    
    if (!confirm(`Вы уверены, что хотите войти как пользователь "${user.username}"?\n\nВы сможете вернуться к своему аккаунту через кнопку в шапке.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/impersonate/${userId}`, {
            method: 'POST',
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showNotification(`✅ Вы вошли как ${data.username}`, 'success');
            // Перезагружаем страницу для обновления состояния
            window.location.href = '/welcome';
        } else {
            showNotification(`❌ ${data.error || 'Ошибка'}`, 'error');
        }
    } catch (error) {
        console.error('Ошибка:', error);
        showNotification('❌ Ошибка при входе как пользователь', 'error');
    }
}

// ========== СЛЕДИМ ЗА ИЗМЕНЕНИЕМ РАЗМЕРА ОКНА ==========
let resizeTimer;
window.addEventListener('resize', function() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function() {
        if (usersList.length > 0) {
            renderUsersTable(usersList);
            filterUsers();
        }
    }, 250);
});

// ========== ИНИЦИАЛИЗАЦИЯ ==========
document.addEventListener('DOMContentLoaded', async function() {
    try {
        const response = await fetch('/api/auth/me', { credentials: 'include' });
        if (response.ok) {
            window.currentUser = await response.json();
            console.log('Текущий пользователь:', window.currentUser);
            loadUsers();
        } else {
            window.location.href = '/';
        }
    } catch (error) {
        console.error('Ошибка:', error);
        window.location.href = '/';
    }
});

// Делаем функции глобальными
window.editUser = editUser;
window.deleteUser = deleteUser;
window.editPermissions = editPermissions;
window.savePermissions = savePermissions;
window.selectAllObjects = selectAllObjects;
window.deselectAllObjects = deselectAllObjects;
window.closeUserModal = closeUserModal;
window.closePermissionsModal = closePermissionsModal;
window.filterUsers = filterUsers;
window.openAddUserModal = openAddUserModal;
window.saveUser = saveUser;
window.loadUsers = loadUsers;
window.generateSnapshots = generateSnapshots;
window.impersonateUser = impersonateUser;
