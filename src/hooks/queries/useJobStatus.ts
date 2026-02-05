import { useQuery } from '@tanstack/react-query';
import { api } from '../../utils/api';
import { JobStatus } from '../../utils/jobPoller';
import { useAuthStore } from '../../stores/authStore';

/**
 * Query hook for polling job status (AlphaFold, RFdiffusion, ProteinMPNN)
 * Uses refetchInterval for automatic polling
 * Only fetches when user is authenticated
 */
export function useJobStatus(
  jobId: string | null,
  jobType: 'alphafold' | 'rfdiffusion' | 'proteinmpnn',
  options?: {
    enabled?: boolean;
    refetchInterval?: number | false;
    maxPollTime?: number; // Maximum polling time in milliseconds
  }
) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { enabled = true, refetchInterval = 3000, maxPollTime = 2 * 60 * 60 * 1000 } = options || {};
  
  return useQuery<JobStatus>({
    queryKey: ['jobStatus', jobType, jobId],
    queryFn: async () => {
      if (!jobId) throw new Error('Job ID is required');
      
      const endpoint = jobType === 'rfdiffusion' 
        ? `/rfdiffusion/status/${jobId}`
        : jobType === 'proteinmpnn'
        ? `/proteinmpnn/status/${jobId}`
        : `/alphafold/status/${jobId}`;
      
      const response = await api.get<JobStatus>(endpoint);
      return response.data;
    },
    enabled: isAuthenticated && enabled && !!jobId, // Only fetch when authenticated
    refetchInterval: (query) => {
      const data = query.state.data;
      
      // Stop polling if job is complete, error, cancelled, or not found
      if (data?.status === 'completed' || data?.status === 'error' || data?.status === 'cancelled' || data?.status === 'not_found') {
        return false;
      }
      
      // Stop polling if max time exceeded
      const startTime = query.state.dataUpdatedAt;
      if (startTime && Date.now() - startTime > maxPollTime) {
        return false;
      }
      
      // Use dynamic interval based on job status
      if (data?.status === 'running') {
        return refetchInterval; // Poll every 3 seconds for running jobs
      }
      
      // Poll every 6 seconds for queued jobs (only if refetchInterval is a number)
      return typeof refetchInterval === 'number' ? refetchInterval * 2 : refetchInterval;
    },
    staleTime: 0, // Always consider data stale for polling
  });
}
