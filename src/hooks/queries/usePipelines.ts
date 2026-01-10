import { useQuery } from '@tanstack/react-query';
import { api } from '../../utils/api';
import { Pipeline } from '../../components/pipeline-canvas/types';

interface PipelinesResponse {
  status: string;
  pipelines: Array<{
    id: string;
    name?: string;
    description?: string;
    status: string;
    message_id?: string;
    conversation_id?: string;
    created_at?: string;
    updated_at?: string;
  }>;
}

interface PipelineResponse {
  status: string;
  pipeline: Pipeline & {
    createdAt?: string | Date;
    updatedAt?: string | Date;
  };
}

/**
 * Query hook for fetching user pipelines
 */
export function usePipelines(conversationId?: string) {
  return useQuery<Pipeline[]>({
    queryKey: ['pipelines', conversationId],
    queryFn: async () => {
      const params = conversationId ? { conversation_id: conversationId } : {};
      const response = await api.get<PipelinesResponse>('/pipelines', { params });
      const backendPipelines = response.data.pipelines || [];
      
      // Fetch full pipeline data for each pipeline
      const pipelinePromises = backendPipelines.map(async (bp) => {
        try {
          const fullResponse = await api.get<PipelineResponse>(`/pipelines/${bp.id}`);
          const fullPipeline = fullResponse.data.pipeline;
          
          // Convert dates
          if (fullPipeline.createdAt) {
            fullPipeline.createdAt = new Date(fullPipeline.createdAt);
          }
          if (fullPipeline.updatedAt) {
            fullPipeline.updatedAt = new Date(fullPipeline.updatedAt);
          }
          
          return fullPipeline as Pipeline;
        } catch (error) {
          console.error(`Failed to load full pipeline ${bp.id}:`, error);
          return null;
        }
      });
      
      const pipelines = await Promise.all(pipelinePromises);
      return pipelines.filter((p): p is Pipeline => p !== null);
    },
    staleTime: 2 * 60 * 1000, // Pipelines can change, cache for 2 minutes
  });
}

/**
 * Query hook for fetching a single pipeline by ID
 */
export function usePipeline(pipelineId: string | null) {
  return useQuery<Pipeline>({
    queryKey: ['pipelines', pipelineId],
    queryFn: async () => {
      if (!pipelineId) throw new Error('Pipeline ID is required');
      const response = await api.get<PipelineResponse>(`/pipelines/${pipelineId}`);
      const pipeline = response.data.pipeline;
      
      // Convert dates
      if (pipeline.createdAt) {
        pipeline.createdAt = new Date(pipeline.createdAt);
      }
      if (pipeline.updatedAt) {
        pipeline.updatedAt = new Date(pipeline.updatedAt);
      }
      
      return pipeline as Pipeline;
    },
    enabled: !!pipelineId,
    staleTime: 2 * 60 * 1000, // Single pipeline cache for 2 minutes
  });
}
