import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../utils/api';
import type { ProteinLabel } from '../../types/chat';

interface RegisterLabelParams {
  sessionId: string;
  kind: string;
  sourceTool?: string;
  fileId?: string;
  jobId?: string;
  metadata?: Record<string, unknown>;
  preferredPrefix?: string;
}

interface RegisterLabelResponse {
  status: string;
  label: ProteinLabel;
}

export function useRegisterProteinLabel() {
  const queryClient = useQueryClient();

  return useMutation<ProteinLabel, Error, RegisterLabelParams>({
    mutationFn: async (params) => {
      const response = await api.post<RegisterLabelResponse>('/proteins', params);
      return response.data.label;
    },
    onSuccess: (_label, variables) => {
      queryClient.invalidateQueries({ queryKey: ['proteinLabels', variables.sessionId] });
    },
  });
}
