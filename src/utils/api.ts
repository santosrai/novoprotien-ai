import axios from 'axios';

// Configure API base URL. Set VITE_API_BASE in your env, e.g.:
const VITE_API_BASE = "http://localhost:8787/api"
// const baseURL = import.meta.env?.VITE_API_BASE || '/api';
const baseURL = VITE_API_BASE || '/api';

export const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
});


// Add request interceptor to inject API key
api.interceptors.request.use((config) => {
  // Get settings from localStorage directly to avoid circular dependencies or hook rules outside components
  try {
    const storageItem = localStorage.getItem('novoprotein-settings-storage');
    if (storageItem) {
      const { state } = JSON.parse(storageItem);
      const apiKey = state?.settings?.api?.key;
      if (apiKey) {
        config.headers['x-api-key'] = apiKey;
      }
    }
  } catch (e) {
    console.warn('Failed to read API key from storage', e);
  }
  return config;
});

export function setApiBaseUrl(url: string) {
  api.defaults.baseURL = url;
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

