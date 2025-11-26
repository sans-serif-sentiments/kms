let cachedBase = null;
function resolveApiBase() {
    if (cachedBase)
        return cachedBase;
    const envBase = import.meta.env.VITE_API_BASE;
    if (envBase) {
        cachedBase = envBase.replace(/\/$/, '');
        return cachedBase;
    }
    const envPort = import.meta.env.VITE_API_PORT;
    if (envPort) {
        cachedBase = `http://127.0.0.1:${envPort}`;
        return cachedBase;
    }
    if (typeof window !== 'undefined') {
        try {
            const stored = window.localStorage.getItem('ai_kms_api_base');
            if (stored) {
                cachedBase = stored.replace(/\/$/, '');
                return cachedBase;
            }
        }
        catch {
            // ignore storage errors
        }
        const { origin, port } = window.location;
        if (port === '5173' || port === '5174') {
            cachedBase = 'http://127.0.0.1:8300';
        }
        else {
            cachedBase = origin.replace(/\/$/, '');
        }
        return cachedBase;
    }
    cachedBase = '';
    return cachedBase;
}
export function setApiBase(base) {
    cachedBase = base.replace(/\/$/, '');
    if (typeof window !== 'undefined') {
        try {
            window.localStorage.setItem('ai_kms_api_base', cachedBase);
        }
        catch {
            // ignore storage errors
        }
    }
}
const API_BASE = resolveApiBase();
async function handleResponse(res) {
    if (res.ok) {
        return res.json();
    }
    let message = `API error ${res.status}`;
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
        try {
            const data = await res.json();
            if (typeof data.detail === 'string') {
                message = data.detail;
            }
            else if (data.detail) {
                message = JSON.stringify(data.detail);
            }
        }
        catch {
            message = message;
        }
    }
    else {
        const text = await res.text();
        if (text)
            message = text;
    }
    throw new Error(message);
}
export function runQuery(payload) {
    return fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then((res) => handleResponse(res));
}
export function fetchHealth() {
    return fetch(`${API_BASE}/health`).then((res) => handleResponse(res));
}
export function fetchGreeting(name) {
    const url = new URL(`${API_BASE}/chat/greet`);
    if (name)
        url.searchParams.set('name', name);
    return fetch(url.toString()).then((res) => handleResponse(res));
}
export function fetchModels() {
    return fetch(`${API_BASE}/chat/models`).then((res) => handleResponse(res));
}
export function uploadDoc(payload) {
    return fetch(`${API_BASE}/upload`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then((res) => handleResponse(res));
}
export function uploadFile(form) {
    return fetch(`${API_BASE}/upload/file`, {
        method: 'POST',
        body: form
    }).then((res) => handleResponse(res));
}
export function createSession(name) {
    return fetch(`${API_BASE}/chat/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    }).then((res) => handleResponse(res));
}
export function loadSession(sessionId) {
    return fetch(`${API_BASE}/chat/session/${sessionId}`).then((res) => handleResponse(res));
}
