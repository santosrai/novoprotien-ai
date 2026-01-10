import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../utils/api';

interface AlphaFoldFoldParams {
  sequence: string;
  parameters?: Record<string, any>;
  jobId: string;
  sessionId?: string;
}

interface AlphaFoldFoldResponse {
  status: 'accepted' | 'queued' | 'running' | 'completed' | 'error';
  job_id?: string;
  message?: string;
  data?: any;
  error?: string;
}

interface AlphaFoldCancelResponse {
  status: string;
  job_id: string;
}

/**
 * Mutation hook for submitting AlphaFold folding jobs
 */
export function useAlphaFoldFold() {
  const queryClient = useQueryClient();
  
  return useMutation<AlphaFoldFoldResponse, Error, AlphaFoldFoldParams>({
    mutationFn: async ({ sequence, parameters, jobId, sessionId }) => {
      const response = await api.post<AlphaFoldFoldResponse>('/alphafold/fold', {
        sequence,
        parameters,
        jobId,
        sessionId,
      });
      
      // Handle 202 Accepted response
      if (response.status === 202 || response.data.status === 'accepted' || response.data.status === 'queued') {
        return response.data;
      }
      
      return response.data;
    },
    onSuccess: (data, variables) => {
      // Invalidate job status query to start polling
      if (data.job_id || variables.jobId) {
        queryClient.invalidateQueries({ queryKey: ['jobStatus', 'alphafold', data.job_id || variables.jobId] });
      }
    },
  });
}

/**
 * Mutation hook for cancelling AlphaFold jobs
 */
export function useAlphaFoldCancel() {
  const queryClient = useQueryClient();
  
  return useMutation<AlphaFoldCancelResponse, Error, string>({
    mutationFn: async (jobId) => {
      const response = await api.post<AlphaFoldCancelResponse>(`/alphafold/cancel/${jobId}`);
      return response.data;
    },
    onSuccess: (_, jobId) => {
      // Invalidate job status query
      queryClient.invalidateQueries({ queryKey: ['jobStatus', 'alphafold', jobId] });
    },
  });
}
