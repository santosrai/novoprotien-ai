import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../utils/api';

interface CreateSessionParams {
  id?: string;
  title?: string;
  ai_agent_id?: string;
}

interface CreateSessionResponse {
  status: string;
  session_id: string;
  message?: string;
}

interface CreateMessageParams {
  sessionId: string;
  message: {
    content: string;
    type?: 'user' | 'ai';
    role?: 'user' | 'assistant' | 'system';
    messageType?: 'text' | 'tool_call' | 'tool_result';
    senderId?: string;
    metadata?: any;
    threeDCanvas?: any;
    pipeline?: any;
    attachments?: any[];
  };
}

interface CreateMessageResponse {
  status: string;
  message_id: string;
  message?: string;
}

interface UpdateSessionParams {
  sessionId: string;
  title?: string;
}

interface UpdateSessionResponse {
  status: string;
  message?: string;
}

/**
 * Mutation hook for creating chat sessions
 */
export function useCreateChatSession() {
  const queryClient = useQueryClient();
  
  return useMutation<CreateSessionResponse, Error, CreateSessionParams>({
    mutationFn: async (params) => {
      const response = await api.post<CreateSessionResponse>('/chat/sessions', params);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate sessions query to refresh list
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });
}

/**
 * Mutation hook for creating chat messages
 */
export function useCreateChatMessage() {
  const queryClient = useQueryClient();
  
  return useMutation<CreateMessageResponse, Error, CreateMessageParams>({
    mutationFn: async ({ sessionId, message }) => {
      const response = await api.post<CreateMessageResponse>(
        `/chat/sessions/${sessionId}/messages`,
        message
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate session messages query to refresh messages
      queryClient.invalidateQueries({ queryKey: ['chatSessions', variables.sessionId, 'messages'] });
      // Also invalidate sessions list to update last activity
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });
}

/**
 * Mutation hook for updating chat sessions (e.g., title)
 */
export function useUpdateChatSession() {
  const queryClient = useQueryClient();
  
  return useMutation<UpdateSessionResponse, Error, UpdateSessionParams>({
    mutationFn: async ({ sessionId, ...updates }) => {
      const response = await api.put<UpdateSessionResponse>(
        `/chat/sessions/${sessionId}`,
        updates
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate both session and sessions list
      queryClient.invalidateQueries({ queryKey: ['chatSessions', variables.sessionId] });
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] });
    },
  });
}
