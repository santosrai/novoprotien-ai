import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../utils/api';

interface RFdiffusionDesignParams {
  parameters: {
    design_mode?: 'unconditional' | 'motif_scaffolding' | 'partial_diffusion';
    contigs?: string;
    hotspot_res?: string[];
    diffusion_steps?: number;
    pdb_id?: string;
    uploadId?: string;
    num_designs?: number;
    [key: string]: any;
  };
  jobId: string;
  sessionId?: string;
}

interface RFdiffusionDesignResponse {
  status: 'accepted' | 'queued' | 'running' | 'completed' | 'error';
  job_id?: string;
  message?: string;
  data?: any;
  error?: string;
}

interface RFdiffusionCancelResponse {
  status: string;
  job_id: string;
}

/**
 * Mutation hook for submitting RFdiffusion design jobs
 */
export function useRFdiffusionDesign() {
  const queryClient = useQueryClient();
  
  return useMutation<RFdiffusionDesignResponse, Error, RFdiffusionDesignParams>({
    mutationFn: async ({ parameters, jobId, sessionId }) => {
      const response = await api.post<RFdiffusionDesignResponse>('/rfdiffusion/design', {
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
        queryClient.invalidateQueries({ queryKey: ['jobStatus', 'rfdiffusion', data.job_id || variables.jobId] });
      }
    },
  });
}

/**
 * Mutation hook for cancelling RFdiffusion jobs
 */
export function useRFdiffusionCancel() {
  const queryClient = useQueryClient();
  
  return useMutation<RFdiffusionCancelResponse, Error, string>({
    mutationFn: async (jobId) => {
      const response = await api.post<RFdiffusionCancelResponse>(`/rfdiffusion/cancel/${jobId}`);
      return response.data;
    },
    onSuccess: (_, jobId) => {
      // Invalidate job status query
      queryClient.invalidateQueries({ queryKey: ['jobStatus', 'rfdiffusion', jobId] });
    },
  });
}
