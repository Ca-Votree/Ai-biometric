/**
 * API Configuration & Helpers
 * Tất cả fetch / WebSocket đều đi qua đây — không hardcode URL ở HTML.
 */
const CONFIG = {
    API_BASE_URL: window.__API_BASE || location.origin,
    API_KEY: '', // Set nếu backend yêu cầu
};

/** Build WebSocket base URL từ HTTP base */
function wsBaseUrl() {
    const proto = CONFIG.API_BASE_URL.startsWith('https') ? 'wss:' : 'ws:';
    const host = CONFIG.API_BASE_URL.replace(/^https?:\/\//, '');
    return `${proto}//${host}`;
}

/**
 * Wrapper fetch cho API — tự thêm API key, parse JSON, throw nếu !ok.
 */
async function apiFetch(endpoint, options = {}) {
    const url = `${CONFIG.API_BASE_URL}${endpoint}`;
    const headers = { ...(options.headers || {}) };
    if (CONFIG.API_KEY) {
        headers['X-API-Key'] = CONFIG.API_KEY;
    }
    const res = await fetch(url, { credentials: 'include', ...options, headers });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const detail = Array.isArray(err.detail)
            ? err.detail.map(item => item.msg || JSON.stringify(item)).join('; ')
            : err.detail;
        const error = new Error(detail || 'Có lỗi xảy ra khi gọi API');
        error.status = res.status;
        throw error;
    }
    return res.json();
}

/** POST JSON helper */
async function apiPost(endpoint, body) {
    return apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
}

/** POST FormData helper (file upload) */
async function apiPostForm(endpoint, formData) {
    return apiFetch(endpoint, { method: 'POST', body: formData });
}

/** Escape HTML — chống XSS khi render user data vào innerHTML */
function escapeHtml(str) {
    if (str == null) return '';
    const d = document.createElement('div');
    d.textContent = String(str);
    return d.innerHTML;
}

/** Toast notification */
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success' ? 'checkmark-circle-outline' : type === 'error' ? 'alert-circle-outline' : 'information-circle-outline';
    toast.innerHTML = `<ion-icon name="${icon}" aria-hidden="true"></ion-icon><span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

/** Toggle sidebar (mobile) */
function toggleSidebar() {
    document.getElementById('sidebar')?.classList.toggle('open');
}

async function loadCurrentUser() {
    const data = await apiFetch('/api/auth/me');
    return data.user;
}

async function logout() {
    try {
        await apiPost('/api/auth/logout', {});
        window.location.replace('/login');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function initializeAccountMenu() {
    const footer = document.querySelector('.sidebar-footer');
    if (!footer) return;
    try {
        const user = await loadCurrentUser();
        const dashboardPath = user.role === 'admin' ? '/admin.html' : '/teacher.html';
        document.querySelectorAll('a[href="index.html"], a[href="/index.html"]').forEach(link => {
            link.href = dashboardPath;
        });
        const account = document.createElement('div');
        account.className = 'sidebar-account';
        const icon = document.createElement('span');
        icon.className = 'sidebar-account-icon';
        icon.innerHTML = `<ion-icon name="${user.role === 'admin' ? 'shield-checkmark-outline' : 'school-outline'}" aria-hidden="true"></ion-icon>`;
        const info = document.createElement('span');
        info.className = 'sidebar-account-info';
        info.innerHTML = `<strong>${escapeHtml(user.full_name)}</strong><span>${user.role === 'admin' ? 'Quản trị viên' : 'Giảng viên'} · ${escapeHtml(user.user_id)}</span>`;
        const button = document.createElement('button');
        button.className = 'sidebar-logout';
        button.type = 'button';
        button.setAttribute('aria-label', 'Đăng xuất');
        button.title = 'Đăng xuất';
        button.innerHTML = '<ion-icon name="log-out-outline" aria-hidden="true"></ion-icon>';
        button.addEventListener('click', logout);
        account.append(icon, info, button);
        footer.prepend(account);
    } catch (error) {
        if (error.status === 401) {
            const next = encodeURIComponent(window.location.pathname + window.location.search);
            window.location.replace(`/login?next=${next}`);
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeAccountMenu);
} else {
    initializeAccountMenu();
}
