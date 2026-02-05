import { useQuery } from '@tanstack/react-query';
import { api, Agent } from '../../utils/api';
import { useAuthStore } from '../../stores/authStore';

/**
 * Query hook for fetching available agents
 * Static config data - fetch once and cache aggressively
 * Only fetches when user is authenticated to avoid wasted API calls
 */
export function useAgents() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  return useQuery<Agent[]>({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await api.get<{ agents: Agent[] }>('/agents');
      return response.data.agents || [];
    },
    enabled: isAuthenticated, // Only fetch when authenticated
    staleTime: Infinity, // Never consider stale - agents are static config
    gcTime: Infinity, // Never garbage collect
    refetchOnMount: false, // Don't refetch on component mount
    refetchOnWindowFocus: false, // Don't refetch on window focus
    refetchOnReconnect: false, // Don't refetch on network reconnect
  });
}
