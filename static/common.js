// static/common.js - полная версия с поддержкой приветственной страницы

// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
let currentUser = null;
let currentAccessLevel = "";
let sessionTimer = null;
let updateInterval = null;

const API_BASE = '/api';
const SESSION_KEY = "sessionData";
const AUTO_UPDATE_INTERVAL = 15 * 60 * 1000; // 15 минут

// ========== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ БЕЗОПАСНОСТИ ==========
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeUrl(url) {
    if (!url) return '#';
    if (url.startsWith('http://') || url.startsWith('https://')) {
        return url;
    }
    return '#';
}

function sanitizeAttribute(value) {
    if (!value) return '';
    return value.replace(/[^\w\s\u0400-\u04FF-]/g, '');
}

// ========== ПЕРЕХВАТЧИК FETCH ДЛЯ ОБРАБОТКИ ОШИБОК АВТОРИЗАЦИИ ==========
const originalFetch = window.fetch;
window.fetch = function(...args) {
    return originalFetch.apply(this, args).then(async response => {
        if (response.status === 401 || response.status === 403) {
            const url = args[0];
            console.warn(`Ошибка авторизации (${response.status}) при запросе: ${url}`);
            // Не перенаправляем на страницу входа, если это запрос к API авторизации
            if (!url.includes('/api/auth') && !url.includes('/api/logout') && window.location.pathname !== '/') {
                window.location.href = '/';
            }
        }
        return response;
    });
};

// ========== ФУНКЦИЯ ОЧИСТКИ СОСТОЯНИЯ ==========
function resetAppState() {
    console.log('Сброс состояния данных приложения...');
    
    if (typeof objects !== 'undefined') objects = [];
    if (typeof vacancyData !== 'undefined') vacancyData = {};
    if (typeof globalOrder !== 'undefined') globalOrder = [];
    if (typeof usersList !== 'undefined') usersList = [];
    
    const officesContainer = document.getElementById('offices-container');
    if (officesContainer) officesContainer.innerHTML = '';
    
    const planFactContainer = document.getElementById('plan-fact-container');
    if (planFactContainer) planFactContainer.innerHTML = '';
    
    const summaryContainer = document.getElementById('summary-container');
    if (summaryContainer) summaryContainer.innerHTML = '';
    
    const resultsContainer = document.getElementById('results');
    if (resultsContainer) resultsContainer.innerHTML = '';
    
    const notifications = document.querySelectorAll('.notification');
    notifications.forEach(n => n.remove());
    
    console.log('Состояние данных сброшено');
}

// ========== АВТОРИЗАЦИЯ ==========
function handleEnterKey(event) {
    if (event.key === 'Enter') {
        checkPassword();
    }
}

async function checkPassword() {
    const username = document.getElementById('login-username')?.value;
    const password = document.getElementById('login-password')?.value;
    const errorMessage = document.getElementById('errorMessage');
    const loginBtn = document.querySelector('.login-btn');
    
    if (!username || !password) {
        if (errorMessage) {
            errorMessage.textContent = 'Введите имя пользователя и пароль';
            errorMessage.style.display = 'block';
        }
        return;
    }
    
    if (loginBtn) {
        loginBtn.disabled = true;
        loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Вход...';
    }
    
    try {
        const response = await fetch('/api/auth/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();
        
        if (data.success) {
            resetAppState();
            
            currentUser = {
                id: data.id,
                username: data.username,
                full_name: data.full_name,
                email: data.email,
                role: data.role,
                role_display: data.role_display,
                is_system_admin: data.is_system_admin,
                module_permissions: data.module_permissions
            };
            currentAccessLevel = data.role;
            startSession(data.role, data.username);
            
            // Перенаправляем на приветственную страницу
            window.location.href = '/welcome';
        } else {
            if (errorMessage) {
                errorMessage.style.display = 'block';
                errorMessage.textContent = data.error || 'Неверное имя пользователя или пароль';
            }
            const passwordInput = document.getElementById('login-password');
            if (passwordInput) {
                passwordInput.value = '';
                passwordInput.focus();
            }
            
            if (response.status === 429) {
                if (errorMessage) {
                    errorMessage.textContent = 'Слишком много попыток. Подождите минуту.';
                    errorMessage.style.color = '#e74c3c';
                }
            }
        }
    } catch (error) {
        console.error('Ошибка авторизации:', error);
        if (errorMessage) {
            errorMessage.style.display = 'block';
            errorMessage.textContent = 'Ошибка соединения с сервером';
            errorMessage.style.color = '#e74c3c';
        }
    } finally {
        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Войти';
        }
    }
}

function startSession(accessLevel, username) {
    currentAccessLevel = accessLevel;
    const sessionData = {
        username: username,
        accessLevel: accessLevel,
        expires: new Date().getTime() + 12 * 60 * 60 * 1000,
        user: currentUser
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(sessionData));
    
    if (sessionTimer) clearTimeout(sessionTimer);
    sessionTimer = setTimeout(() => {
        showNotification("Время сессии истекло. Пожалуйста, войдите снова.", 'warning');
        logout();
    }, 12 * 60 * 60 * 1000);
}

function checkSession() {
    const sessionData = localStorage.getItem(SESSION_KEY);
    
    // На странице входа - пропускаем
    if (window.location.pathname === '/') {
        return true;
    }
    
    if (!sessionData) {
        window.location.href = '/';
        return false;
    }
    
    try {
        const session = JSON.parse(sessionData);
        if (new Date().getTime() > session.expires) {
            localStorage.removeItem(SESSION_KEY);
            window.location.href = '/';
            return false;
        }
        currentAccessLevel = session.accessLevel;
        currentUser = session.user;
        
        if (sessionTimer) clearTimeout(sessionTimer);
        const remainingTime = session.expires - new Date().getTime();
        sessionTimer = setTimeout(() => {
            showNotification("Время сессии истекло. Пожалуйста, войдите снова.", 'warning');
            logout();
        }, remainingTime);
        
        return true;
    } catch (e) {
        localStorage.removeItem(SESSION_KEY);
        window.location.href = '/';
        return false;
    }
}

async function verifySession() {
    if (!currentUser) return false;
    
    try {
        const response = await fetch('/api/auth/me', { credentials: 'include' });
        if (response.ok) {
            const data = await response.json();
            currentUser = { ...currentUser, ...data };
            // Обновляем сессию в localStorage
            const sessionData = localStorage.getItem(SESSION_KEY);
            if (sessionData) {
                const session = JSON.parse(sessionData);
                session.user = currentUser;
                localStorage.setItem(SESSION_KEY, JSON.stringify(session));
            }
            return true;
        } else {
            logout();
            return false;
        }
    } catch (error) {
        console.error('Ошибка проверки сессии:', error);
        return false;
    }
}

function showLoginModal() {
    const loginModal = document.getElementById('loginModal');
    if (loginModal) {
        loginModal.style.display = 'flex';
        document.body.classList.add('modal-open');
    }
    const usernameInput = document.getElementById('login-username');
    if (usernameInput) {
        usernameInput.value = '';
        usernameInput.focus();
    }
    const passwordInput = document.getElementById('login-password');
    if (passwordInput) passwordInput.value = '';
}

async function logout() {
    stopAutoUpdate();
    
    try {
        await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
    } catch (e) {
        console.error('Ошибка при выходе:', e);
    }
    
    localStorage.removeItem(SESSION_KEY);
    resetAppState();
    currentUser = null;
    currentAccessLevel = "";
    window.location.href = '/';
}

// ========== ОБНОВЛЕНИЕ ==========
function startAutoUpdate() {
    if (updateInterval) clearInterval(updateInterval);
    updateInterval = setInterval(async () => {
        // Проверяем на какой странице мы находимся
        if (window.location.pathname === '/dashboard') {
            if (typeof loadDashboardForDate === 'function') {
                const date = document.getElementById('date-picker')?.value || getTodayDate();
                await loadDashboardForDate(date);
            }
        } else if (window.location.pathname === '/selection') {
            if (typeof loadSelectionData === 'function') {
                await loadSelectionData();
            }
        }
    }, AUTO_UPDATE_INTERVAL);
}

function stopAutoUpdate() {
    if (updateInterval) {
        clearInterval(updateInterval);
        updateInterval = null;
    }
}

async function manualRefresh() {
    const btn = document.getElementById('refresh-button');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="refresh-icon">↻</span> Обновление...';
    }
    
    try {
        if (window.location.pathname === '/dashboard') {
            const date = document.getElementById('date-picker')?.value || getTodayDate();
            await fetch('/api/update-requirements', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ date })
            });
            if (typeof loadDashboardForDate === 'function') {
                await loadDashboardForDate(date);
            }
        } else if (window.location.pathname === '/selection') {
            if (typeof loadSelectionData === 'function') {
                await loadSelectionData();
            }
        }
        showNotification('✅ Данные обновлены', 'success');
    } catch (error) {
        showNotification('❌ Ошибка обновления', 'error');
    }
    
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span class="refresh-icon">↻</span> Обновить';
    }
}

// ========== УВЕДОМЛЕНИЯ ==========
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = escapeHtml(message);
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

function showError(message) {
    showNotification(message, 'error');
}

function getTodayDate() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
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

function getRoleColor(role) {
    switch(role) {
        case 'admin': return '#e74c3c';
        case 'manager': return '#f39c12';
        case 'viewer': return '#3498db';
        default: return '#95a5a6';
    }
}

// ========== ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ СТРАНИЦЫ ==========
async function initPage() {
    const path = window.location.pathname;
    
    console.log('Инициализация страницы:', path);
    
    // На странице входа - не проверяем сессию (она уже проверяется в index.html)
    if (path === '/') {
        return;
    }
    
    // Проверяем сессию
    const hasSession = checkSession();
    if (!hasSession) {
        return;
    }
    
    // Проверяем сессию на сервере
    const isValid = await verifySession();
    if (!isValid) {
        return;
    }
    
    // Отображаем информацию о пользователе
    const userInfo = document.getElementById('userInfo');
    if (userInfo && currentUser) {
        let roleClass = 'viewer';
        let roleIcon = '👤';
        
        if (currentUser.is_system_admin) {
            roleClass = 'system-admin';
            roleIcon = '👑';
        } else if (currentUser.role === 'admin') {
            roleClass = 'admin';
            roleIcon = '⭐';
        } else if (currentUser.role === 'manager') {
            roleClass = 'manager';
            roleIcon = '📋';
        }
        
        userInfo.innerHTML = `
            <div class="user-info-container">
                <div class="user-badge ${roleClass}">
                    ${roleIcon} ${escapeHtml(currentUser.full_name || currentUser.username)}
                    <span class="user-role">${escapeHtml(currentUser.role_display)}</span>
                </div>
                <button class="logout-button" onclick="logout()">
                    <i class="fas fa-sign-out-alt"></i> Выйти
                </button>
            </div>
        `;
    }
    
    // Запускаем автообновление только на страницах с данными
    if (path === '/dashboard' || path === '/selection') {
        startAutoUpdate();
    }
}

// ========== ЭКСПОРТ ГЛОБАЛЬНЫХ ФУНКЦИЙ ==========
window.checkPassword = checkPassword;
window.handleEnterKey = handleEnterKey;
window.logout = logout;
window.manualRefresh = manualRefresh;
window.showNotification = showNotification;
window.showError = showError;
window.getTodayDate = getTodayDate;
window.escapeHtml = escapeHtml;
window.escapeUrl = escapeUrl;
window.sanitizeAttribute = sanitizeAttribute;
window.formatDate = formatDate;
window.formatDateTime = formatDateTime;
window.getRoleColor = getRoleColor;

// Запускаем инициализацию после загрузки DOM
document.addEventListener('DOMContentLoaded', initPage);