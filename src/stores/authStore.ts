import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { api } from '../utils/api';

export interface User {
  id: string;
  email: string;
  username: string;
  role: 'user' | 'admin' | 'moderator';
  credits: number;
  email_verified?: boolean;
  created_at?: string;
  last_login?: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  signin: (email: string, password: string) => Promise<void>;
  signup: (email: string, username: string, password: string) => Promise<void>;
  signout: () => void;
  refreshAccessToken: () => Promise<void>;
  updateUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      signin: async (email: string, password: string) => {
        try {
          const response = await api.post('/auth/signin', { email, password });
          
          // Handle response - check if status is success
          if (response.data.status !== 'success') {
            throw new Error(response.data.detail || 'Sign in failed');
          }
          
          const { access_token, refresh_token, user } = response.data;
          
          if (!access_token || !refresh_token || !user) {
            throw new Error('Invalid response from server');
          }
          
          set({
            user,
            accessToken: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
          });
          
          // Clear chat history and sync from backend for the new user
          // Import dynamically to avoid circular dependency
          // Use immediate execution to prevent race conditions
          (async () => {
            try {
              const { useChatHistoryStore } = await import('./chatHistoryStore');
              const chatStore = useChatHistoryStore.getState();
              // Clear local sessions first (synchronously)
              chatStore.clearAllSessions();
              // Small delay to ensure state is cleared, then sync from backend
              await new Promise(resolve => setTimeout(resolve, 50));
              // Then sync from backend (will be empty if user has no sessions)
              await chatStore.syncSessions();
            } catch (err) {
              console.error('Failed to sync chat history on signin:', err);
            }
          })();
          
          // Clear pipeline data and sync from backend
          (async () => {
            try {
              const { usePipelineStore } = await import('../components/pipeline-canvas/store/pipelineStore');
              const pipelineStore = usePipelineStore.getState();
              // Clear local pipelines first
              pipelineStore.clearPipeline();
              // Clear saved pipelines from state
              usePipelineStore.setState({ savedPipelines: [] });
              
              // Wait a bit longer to ensure PipelineProvider has set dependencies
              // Then explicitly sync from backend
              await new Promise(resolve => setTimeout(resolve, 500));
              
              // Try to sync from backend if dependencies are available
              const { api } = await import('../utils/api');
              if (api && user) {
                try {
                  console.log('[AuthStore] Syncing pipelines from backend after login');
                  await pipelineStore.syncPipelines({ 
                    apiClient: api, 
                    authState: { user, isAuthenticated: true } 
                  });
                } catch (syncError) {
                  console.warn('[AuthStore] Pipeline sync failed (will retry when PipelineProvider mounts):', syncError);
                  // Don't throw - PipelineProvider will retry sync when it mounts
                }
              }
            } catch (err) {
              console.error('Failed to clear/sync pipelines on signin:', err);
            }
          })();
        } catch (error: any) {
          const message = error.response?.data?.detail || error.message || 'Sign in failed';
          throw new Error(message);
        }
      },

      signup: async (email: string, username: string, password: string) => {
        try {
          await api.post('/auth/signup', { email, username, password });
          // Auto sign in after signup
          await get().signin(email, password);
        } catch (error: any) {
          const message = error.response?.data?.detail || error.message || 'Sign up failed';
          throw new Error(message);
        }
      },

      signout: () => {
        const { refreshToken } = get();
        // Try to invalidate refresh token on server
        if (refreshToken) {
          api.post('/auth/signout', { refresh_token: refreshToken }).catch(() => {
            // Ignore errors on signout
          });
        }
        
        // Clear chat history on signout
        setTimeout(async () => {
          try {
            const { useChatHistoryStore } = await import('./chatHistoryStore');
            useChatHistoryStore.getState().clearAllSessions();
          } catch (err) {
            console.error('Failed to clear chat history on signout:', err);
          }
        }, 100);
        
        // Clear pipeline data on signout
        setTimeout(async () => {
          try {
            const { usePipelineStore } = await import('../components/pipeline-canvas/store/pipelineStore');
            const pipelineStore = usePipelineStore.getState();
            pipelineStore.clearPipeline();
            usePipelineStore.setState({ savedPipelines: [] });
          } catch (err) {
            console.error('Failed to clear pipelines on signout:', err);
          }
        }, 100);
        
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      },

      refreshAccessToken: async () => {
        // NOTE: Token refresh is primarily handled by the axios interceptor
        // in api.ts with deduplication. This method is kept for backward
        // compatibility but should rarely be called directly.
        const { refreshToken } = get();
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }
        try {
          // Use raw axios to avoid triggering the interceptor loop
          const { default: axios } = await import('axios');
          const baseURL = api.defaults.baseURL;
          const response = await axios.post(`${baseURL}/auth/refresh`, { refresh_token: refreshToken });
          const { access_token } = response.data;
          set({ accessToken: access_token });
        } catch (error) {
          // Refresh failed, sign out
          get().signout();
          throw error;
        }
      },

      updateUser: (user: User) => {
        set({ user });
      },
    }),
    {
      name: 'novoprotein-auth-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);

