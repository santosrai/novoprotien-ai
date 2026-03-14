import { useQuery } from '@tanstack/react-query';
import { api } from '../../utils/api';
import { useAuthStore } from '../../stores/authStore';
import type { ProteinLabel } from '../../types/chat';

interface ProteinLabelsResponse {
  status: string;
  labels: ProteinLabel[];
}

export function useProteinLabels(sessionId: string | null | undefined) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return useQuery<ProteinLabel[]>({
    queryKey: ['proteinLabels', sessionId],
    queryFn: async () => {
      if (!sessionId) return [];
      const response = await api.get<ProteinLabelsResponse>('/proteins', {
        params: { sessionId },
      });
      if (response.data?.status === 'success') {
        return response.data.labels || [];
      }
      return [];
    },
    enabled: isAuthenticated && !!sessionId,
    staleTime: 30 * 1000,
  });
}
