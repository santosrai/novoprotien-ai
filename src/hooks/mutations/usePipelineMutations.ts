import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../utils/api';
import { Pipeline } from '../../components/pipeline-canvas/types';

interface CreatePipelineParams {
  id?: string;
  name: string;
  description?: string;
  nodes: any[];
  edges: Array<{ source: string; target: string }>;
  message_id?: string;
  conversation_id?: string;
}

interface UpdatePipelineParams extends CreatePipelineParams {
  id: string;
}

interface PipelineResponse {
  status: string;
  pipeline?: Pipeline;
  id?: string;
  message?: string;
}

/**
 * Mutation hook for creating pipelines
 */
export function useCreatePipeline() {
  const queryClient = useQueryClient();
  
  return useMutation<PipelineResponse, Error, CreatePipelineParams>({
    mutationFn: async (pipelineData) => {
      const response = await api.post<PipelineResponse>('/pipelines', pipelineData);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate pipelines query to refresh list
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
    },
  });
}

/**
 * Mutation hook for updating pipelines
 */
export function useUpdatePipeline() {
  const queryClient = useQueryClient();
  
  return useMutation<PipelineResponse, Error, UpdatePipelineParams>({
    mutationFn: async ({ id, ...pipelineData }) => {
      const response = await api.put<PipelineResponse>(`/pipelines/${id}`, pipelineData);
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate both list and specific pipeline queries
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
      queryClient.invalidateQueries({ queryKey: ['pipelines', variables.id] });
    },
  });
}

/**
 * Mutation hook for deleting pipelines
 */
export function useDeletePipeline() {
  const queryClient = useQueryClient();
  
  return useMutation<void, Error, string>({
    mutationFn: async (pipelineId) => {
      await api.delete(`/pipelines/${pipelineId}`);
    },
    onSuccess: () => {
      // Invalidate pipelines query to refresh list
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
    },
  });
}
