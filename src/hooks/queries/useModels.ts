import { useQuery } from '@tanstack/react-query';
import { api, Model } from '../../utils/api';

/**
 * Query hook for fetching available models
 */
export function useModels() {
  return useQuery<Model[]>({
    queryKey: ['models'],
    queryFn: async () => {
      const response = await api.get<{ models: Model[] }>('/models');
      return response.data.models || [];
    },
    staleTime: 10 * 60 * 1000, // Models don't change often, cache for 10 minutes
  });
}
