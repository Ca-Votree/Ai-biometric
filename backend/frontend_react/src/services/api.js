const API_BASE = '';

export async function apiFetch(endpoint, options = {}) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Lỗi kết nối server' }));
        throw new Error(err.detail || 'Lỗi API');
    }
    return res.json();
}

export async function apiPost(endpoint, data) {
    return apiFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function apiPatch(endpoint, data) {
    return apiFetch(endpoint, {
        method: 'PATCH',
        body: JSON.stringify(data),
    });
}

export async function apiDownload(endpoint) {
    const res = await fetch(`${API_BASE}${endpoint}`);
    if (!res.ok) throw new Error('Không thể tải báo cáo');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = endpoint.split('/').pop() || 'bao-cao.csv';
    link.click();
    URL.revokeObjectURL(url);
}

export async function apiPostFormData(endpoint, formData) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        body: formData,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Lỗi upload' }));
        throw new Error(err.detail || 'Lỗi API');
    }
    return res.json();
}
