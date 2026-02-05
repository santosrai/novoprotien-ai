import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../utils/api';
import { useAuthStore, User } from '../../stores/authStore';

interface SignInResponse {
  status: string;
  access_token: string;
  refresh_token: string;
  user: User;
}

interface SignUpResponse {
  status: string;
  message: string;
}

interface RefreshTokenResponse {
  access_token: string;
}

/**
 * Mutation hook for user sign in
 */
export function useSignIn() {
  const queryClient = useQueryClient();
  
  return useMutation<SignInResponse, Error, { email: string; password: string }>({
    mutationFn: async ({ email, password }) => {
      const response = await api.post<SignInResponse>('/auth/signin', { email, password });
      if (response.data.status !== 'success') {
        throw new Error('Sign in failed');
      }
      return response.data;
    },
    onSuccess: async () => {
      // Update auth store using Zustand pattern
      // Note: We'll keep the existing signin method in authStore for now
      // This mutation will be used alongside it during migration
      
      // Invalidate and refetch user-dependent queries
      queryClient.invalidateQueries({ queryKey: ['files'] });
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });
}

/**
 * Mutation hook for user sign up
 */
export function useSignUp() {
  const signIn = useSignIn();
  
  return useMutation<SignUpResponse, Error, { email: string; username: string; password: string }>({
    mutationFn: async ({ email, username, password }) => {
      const response = await api.post<SignUpResponse>('/auth/signup', { email, username, password });
      return response.data;
    },
    onSuccess: async (_, variables) => {
      // Auto sign in after signup
      await signIn.mutateAsync({ email: variables.email, password: variables.password });
    },
  });
}

/**
 * Mutation hook for user sign out
 */
export function useSignOut() {
  const queryClient = useQueryClient();
  
  return useMutation<void, Error, void>({
    mutationFn: async () => {
      const state = useAuthStore.getState();
      if (state.refreshToken) {
        try {
          await api.post('/auth/signout', { refresh_token: state.refreshToken });
        } catch (error) {
          // Ignore errors on signout
          console.warn('Signout request failed:', error);
        }
      }
    },
    onSuccess: () => {
      // Clear auth store
      useAuthStore.getState().signout();
      
      // Clear all queries
      queryClient.clear();
    },
  });
}

/**
 * Mutation hook for refreshing access token
 */
export function useRefreshToken() {
  return useMutation<RefreshTokenResponse, Error, void>({
    mutationFn: async () => {
      const state = useAuthStore.getState();
      if (!state.refreshToken) {
        throw new Error('No refresh token available');
      }
      const response = await api.post<RefreshTokenResponse>('/auth/refresh', { refresh_token: state.refreshToken });
      return response.data;
    },
    onSuccess: () => {
      // Update access token in store
      // Note: We'll keep the existing refreshAccessToken method in authStore for now
      // This mutation will be used alongside it during migration
    },
    onError: () => {
      // Refresh failed, sign out
      useAuthStore.getState().signout();
    },
  });
}
