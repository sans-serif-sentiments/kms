export type ChatRole = 'user' | 'assistant';

export interface ChatHistoryEntry {
  role: ChatRole;
  content: string;
}

export interface StoredMessage extends ChatHistoryEntry {
  metadata?: Record<string, unknown>;
}

export interface QueryPayload {
  question: string;
  top_k?: number;
  debug?: boolean;
  history?: ChatHistoryEntry[];
  session_id?: string;
  model?: string;
  min_score_threshold?: number;
  allow_external?: boolean;
}

export interface SourceInfo {
  knowledge_unit_id: string;
  title: string;
  source_path: string;
  section: string;
  version: string;
  updated_at: string;
  web_url?: string;
}

export interface QueryResponse {
  answer: string;
  sources: SourceInfo[];
  debug?: unknown;
  model?: string;
  session_id?: string;
  confidence?: string;
  source_type?: string;
}

export interface HealthInfo {
  status: string;
  repo: string;
  units: number;
  last_indexed_at?: string;
}

export interface ModelList {
  default: string;
  allowed: string[];
}

export interface UploadPayload {
  id: string;
  title: string;
  category: string;
  body: string;
  tags?: string[];
  contacts?: Record<string, unknown>[];
  related_units?: string[];
  systems?: string[];
  version?: string;
  dry_run?: boolean;
}

export interface UploadResponse {
  message: string;
  path?: string;
  paths?: string[];
  indexed: number;
  skipped: number;
  deleted: number;
  chunks: number;
  preview_text?: string | null;
}
let cachedBase: string | null = null;

function resolveApiBase(): string {
  if (cachedBase) return cachedBase;
  const envBase = import.meta.env.VITE_API_BASE as string | undefined;
  if (envBase) {
    cachedBase = envBase.replace(/\/$/, '');
    return cachedBase;
  }
  const envPort = import.meta.env.VITE_API_PORT as string | undefined;
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
    } catch {
      // ignore storage errors
    }
    const { origin, port } = window.location;
    if (port === '5173' || port === '5174') {
      cachedBase = 'http://127.0.0.1:8300';
    } else {
      cachedBase = origin.replace(/\/$/, '');
    }
    return cachedBase;
  }
  cachedBase = '';
  return cachedBase;
}

export function setApiBase(base: string) {
  cachedBase = base.replace(/\/$/, '');
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem('ai_kms_api_base', cachedBase);
    } catch {
      // ignore storage errors
    }
  }
}

const API_BASE = resolveApiBase();

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) {
    return res.json() as Promise<T>;
  }
  let message = `API error ${res.status}`;
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') {
        message = data.detail;
      } else if (data.detail) {
        message = JSON.stringify(data.detail);
      }
    } catch {
      message = message;
    }
  } else {
    const text = await res.text();
    if (text) message = text;
  }
  throw new Error(message);
}

export function runQuery(payload: QueryPayload): Promise<QueryResponse> {
  return fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then((res) => handleResponse<QueryResponse>(res));
}

export function fetchHealth(): Promise<HealthInfo> {
  return fetch(`${API_BASE}/health`).then((res) => handleResponse<HealthInfo>(res));
}

export function fetchGreeting(name?: string): Promise<{ message: string }> {
  const url = new URL(`${API_BASE}/chat/greet`);
  if (name) url.searchParams.set('name', name);
  return fetch(url.toString()).then((res) => handleResponse<{ message: string }>(res));
}

export function fetchModels(): Promise<ModelList> {
  return fetch(`${API_BASE}/chat/models`).then((res) => handleResponse<ModelList>(res));
}

export function uploadDoc(payload: UploadPayload): Promise<UploadResponse> {
  return fetch(`${API_BASE}/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then((res) => handleResponse<UploadResponse>(res));
}

export function uploadFile(form: FormData): Promise<UploadResponse> {
  return fetch(`${API_BASE}/upload/file`, {
    method: 'POST',
    body: form
  }).then((res) => handleResponse<UploadResponse>(res));
}

export function createSession(name?: string): Promise<{ session_id: string; greeting: string; name?: string }> {
  return fetch(`${API_BASE}/chat/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  }).then((res) => handleResponse<{ session_id: string; greeting: string; name?: string }>(res));
}

export function loadSession(sessionId: string): Promise<{ session_id: string; name?: string; messages: StoredMessage[] }> {
  return fetch(`${API_BASE}/chat/session/${sessionId}`).then((res) =>
    handleResponse<{ session_id: string; name?: string; messages: StoredMessage[] }>(res)
  );
}
