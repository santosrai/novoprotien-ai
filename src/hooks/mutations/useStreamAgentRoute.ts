import { useMutation } from '@tanstack/react-query';
import { streamAgentRoute, StreamChunk } from '../../utils/api';

interface StreamAgentRouteParams {
  input: string;
  currentCode?: string;
  history?: Array<{ type: string; content: string }>;
  selection?: any;
  selections?: any[];
  agentId?: string;
  model?: string;
  uploadedFileId?: string;
}

/**
 * Mutation hook for streaming agent route responses
 * Uses a custom streaming handler since React Query doesn't natively support streaming
 */
export function useStreamAgentRoute() {
  return useMutation<AsyncGenerator<StreamChunk, void, unknown>, Error, StreamAgentRouteParams>({
    mutationFn: async (params) => {
      // Return the generator directly - the component will iterate over it
      return streamAgentRoute(params);
    },
  });
}
