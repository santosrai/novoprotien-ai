import { useQuery } from '@tanstack/react-query';
import { api, Model } from '../../utils/api';
import { useAuthStore } from '../../stores/authStore';

/**
 * Query hook for fetching available models
 * Static config data - fetch once and cache aggressively
 * Only fetches when user is authenticated to avoid wasted API calls
 */
export function useModels() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  return useQuery<Model[]>({
    queryKey: ['models'],
    queryFn: async () => {
      const response = await api.get<{ models: Model[] }>('/models');
      return response.data.models || [];
    },
    enabled: isAuthenticated, // Only fetch when authenticated
    staleTime: Infinity, // Never consider stale - models are static config
    gcTime: Infinity, // Never garbage collect
    refetchOnMount: false, // Don't refetch on component mount
    refetchOnWindowFocus: false, // Don't refetch on window focus
    refetchOnReconnect: false, // Don't refetch on network reconnect
  });
}
