import axios from 'axios';
import type { ValidationReport } from '../types/validation';

// Configure API base URL. Set VITE_API_BASE in your env, e.g.:
// Prefer environment variable, fallback to relative path for flexibility
const VITE_API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://localhost:8787/api";
const baseURL = VITE_API_BASE || '/api';

export const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
});


// Add request interceptor to inject JWT token
api.interceptors.request.use((config) => {
  // Get auth token from localStorage
  try {
    const authStorage = localStorage.getItem('novoprotein-auth-storage');
    if (authStorage) {
      const { state } = JSON.parse(authStorage);
      const accessToken = state?.accessToken;
      if (accessToken) {
        config.headers['Authorization'] = `Bearer ${accessToken}`;
      }
    }
  } catch (e) {
    console.warn('Failed to read auth token from storage', e);
  }
  
  // Legacy: Also check for API key (for backward compatibility)
  try {
    const storageItem = localStorage.getItem('novoprotein-settings-storage');
    if (storageItem) {
      const { state } = JSON.parse(storageItem);
      const apiKey = state?.settings?.api?.key;
      if (apiKey && !config.headers['Authorization']) {
        config.headers['x-api-key'] = apiKey;
      }
    }
  } catch (e) {
    // Ignore
  }
  
  return config;
});

// --- Deduplication for token refresh ---
// Ensures only ONE refresh request is in-flight at a time.
// All concurrent 401 responses queue behind the same promise.
let refreshPromise: Promise<string | null> | null = null;
let hasRedirected = false;

function redirectToSignin() {
  if (hasRedirected) return;
  hasRedirected = true;
  // Clear auth storage
  try { localStorage.removeItem('novoprotein-auth-storage'); } catch (_) { /* ignore */ }
  // Only redirect if not already on auth pages
  if (!window.location.pathname.startsWith('/signin') && !window.location.pathname.startsWith('/signup')) {
    window.location.href = '/signin';
  }
}

function doRefreshToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const authStorage = localStorage.getItem('novoprotein-auth-storage');
      if (!authStorage) return null;

      const { state } = JSON.parse(authStorage);
      const refreshToken = state?.refreshToken;
      if (!refreshToken) return null;

      // Use raw axios (NOT the intercepted `api` instance) to avoid loops
      const response = await axios.post(`${baseURL}/auth/refresh`, {
        refresh_token: refreshToken,
      });

      const { access_token } = response.data;
      if (!access_token) return null;

      // Update stored token
      const updatedState = { ...state, accessToken: access_token };
      localStorage.setItem('novoprotein-auth-storage', JSON.stringify({ state: updatedState }));
      return access_token;
    } catch (_) {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

// Add response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 Unauthorized - try to refresh token ONCE
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const newToken = await doRefreshToken();

      if (newToken) {
        // Retry original request with the fresh token
        originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
        return api(originalRequest);
      }

      // Refresh failed or no refresh token — redirect once
      redirectToSignin();
      return Promise.reject(error);
    }

    // Handle 402 Payment Required (insufficient credits)
    if (error.response?.status === 402) {
      // This will be handled by the component
      return Promise.reject(error);
    }

    return Promise.reject(error);
  }
);

export function setApiBaseUrl(url: string) {
  api.defaults.baseURL = url;
}

/**
 * Get the current authentication token from localStorage.
 * This is useful for fetch() calls that need to include the Authorization header.
 */
export function getAuthToken(): string | null {
  try {
    const authStorage = localStorage.getItem('novoprotein-auth-storage');
    if (authStorage) {
      const { state } = JSON.parse(authStorage);
      return state?.accessToken || null;
    }
  } catch (e) {
    console.warn('Failed to read auth token from storage', e);
  }
  return null;
}

/**
 * Get headers for authenticated fetch requests.
 * Includes Authorization header if token is available.
 */
export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  description: string;
  context_length: number;
  pricing: {
    prompt: string;
    completion: string;
  };
  architecture?: Record<string, any>;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  kind: string;
  category: string;
}

export async function fetchModels(): Promise<Model[]> {
  try {
    const response = await api.get<{ models: Model[] }>('/models');
    const models = response.data.models || [];
    console.log('[API] Fetched models:', models.length);
    return models;
  } catch (error: any) {
    console.error('[API] Failed to fetch models:', error);
    if (error.response) {
      console.error('[API] Response status:', error.response.status);
      console.error('[API] Response data:', error.response.data);
    }
    return [];
  }
}

export async function fetchAgents(): Promise<Agent[]> {
  try {
    const response = await api.get<{ agents: Agent[] }>('/agents');
    return response.data.agents || [];
  } catch (error) {
    console.error('Failed to fetch agents:', error);
    return [];
  }
}

export interface StreamChunk {
  type: 'thinking_step' | 'content' | 'complete' | 'error';
  data: any;
}

/**
 * Stream agent route responses for thinking models.
 * Yields chunks as they arrive from the server.
 */
export interface StreamAgentRoutePayload {
  input: string;
  currentCode?: string;
  history?: Array<{ type: string; content: string }>;
  selection?: any;
  selections?: any[];
  agentId?: string;
  model?: string;
  uploadedFileId?: string;
  currentStructureOrigin?: any;
  uploadedFile?: any;
  structureMetadata?: any;
  pipeline_id?: string;
  pipeline_data?: any;
}

export async function* streamAgentRoute(payload: StreamAgentRoutePayload): AsyncGenerator<StreamChunk, void, unknown> {
  // Build headers with auth (required for all API calls)
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
  };

  // Abort controller with 90s timeout to prevent infinite loading
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 90_000);

  let response: Response;
  try {
    // Make streaming request
    response = await fetch(`${baseURL}/agents/route/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (error: any) {
    clearTimeout(timeoutId);
    yield {
      type: 'error',
      data: { error: error.name === 'AbortError' ? 'Request timed out' : 'Network error', detail: error.message },
    };
    return;
  }

  if (!response.ok) {
    clearTimeout(timeoutId);
    const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
    yield {
      type: 'error',
      data: { error: errorData.error || 'Request failed', detail: errorData.detail },
    };
    return;
  }

  // Read stream
  const reader = response.body?.getReader();
  if (!reader) {
    clearTimeout(timeoutId);
    yield {
      type: 'error',
      data: { error: 'No response body' },
    };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      // Decode chunk and add to buffer
      buffer += decoder.decode(value, { stream: true });

      // Process complete lines (newline-delimited JSON)
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
          continue;
        }

        try {
          const chunk: StreamChunk = JSON.parse(trimmed);
          yield chunk;

          // If we get a complete or error, we're done
          if (chunk.type === 'complete' || chunk.type === 'error') {
            return;
          }
        } catch (e) {
          console.warn('[Stream] Failed to parse chunk:', trimmed, e);
          // Continue processing other chunks
        }
      }
    }

    // Process any remaining buffer
    if (buffer.trim()) {
      try {
        const chunk: StreamChunk = JSON.parse(buffer.trim());
        yield chunk;
      } catch (e) {
        console.warn('[Stream] Failed to parse final chunk:', buffer, e);
      }
    }
  } catch (error: any) {
    console.error('[Stream] Error reading stream:', error);
    const isTimeout = error.name === 'AbortError';
    yield {
      type: 'error',
      data: { error: isTimeout ? 'Request timed out' : 'Stream read error', detail: error.message },
    };
  } finally {
    clearTimeout(timeoutId);
    reader.releaseLock();
  }
}

/**
 * Validate a protein structure and return a detailed validation report.
 * Provide either pdbContent (raw PDB string) or fileId (server-side file reference).
 */
export async function validateStructure(
  pdbContent?: string,
  fileId?: string,
  sessionId?: string,
): Promise<ValidationReport> {
  const response = await api.post<ValidationReport>('/validation/validate', {
    pdb_content: pdbContent,
    file_id: fileId,
    session_id: sessionId,
  });
  return response.data;
}
