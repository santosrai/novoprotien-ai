import { useQuery } from '@tanstack/react-query';
import { api, Agent } from '../../utils/api';

/**
 * Query hook for fetching available agents
 */
export function useAgents() {
  return useQuery<Agent[]>({
    queryKey: ['agents'],
    queryFn: async () => {
      const response = await api.get<{ agents: Agent[] }>('/agents');
      return response.data.agents || [];
    },
    staleTime: 10 * 60 * 1000, // Agents don't change often, cache for 10 minutes
  });
}
