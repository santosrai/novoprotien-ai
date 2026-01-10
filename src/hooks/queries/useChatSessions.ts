import { useQuery } from '@tanstack/react-query';
import { api } from '../../utils/api';
import { ChatSession, Message } from '../../stores/chatHistoryStore';

interface SessionsResponse {
  status: string;
  sessions: Array<{
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
  }>;
}

interface MessagesResponse {
  status: string;
  messages: Array<{
    id: string;
    session_id?: string;
    conversation_id?: string;
    sender_id?: string;
    content: string;
    role: 'user' | 'assistant' | 'system';
    message_type?: string;
    created_at: string;
    metadata?: any;
    threeDCanvas?: any;
    pipeline?: any;
    attachments?: any[];
  }>;
}

/**
 * Query hook for fetching user chat sessions
 */
export function useChatSessions() {
  return useQuery<ChatSession[]>({
    queryKey: ['chatSessions'],
    queryFn: async () => {
      const response = await api.get<SessionsResponse>('/chat/sessions');
      const backendSessions = response.data.sessions || [];
      
      return backendSessions.map((bs) => ({
        id: bs.id,
        title: bs.title || 'New Chat',
        createdAt: new Date(bs.created_at),
        lastModified: new Date(bs.updated_at || bs.created_at),
        messages: [], // Messages loaded separately
        metadata: {
          messageCount: 0,
          lastActivity: new Date(bs.updated_at || bs.created_at),
          starred: false,
          tags: [],
        },
      }));
    },
    staleTime: 1 * 60 * 1000, // Sessions can change, cache for 1 minute
  });
}

/**
 * Query hook for fetching messages in a chat session
 */
export function useChatSession(sessionId: string | null) {
  return useQuery<{ session: ChatSession; messages: Message[] }>({
    queryKey: ['chatSessions', sessionId, 'messages'],
    queryFn: async () => {
      if (!sessionId) throw new Error('Session ID is required');
      
      // Fetch session details
      const sessionResponse = await api.get<{ session: any }>(`/chat/sessions/${sessionId}`);
      const sessionData = sessionResponse.data.session;
      
      // Fetch messages
      const messagesResponse = await api.get<MessagesResponse>(`/chat/sessions/${sessionId}/messages`);
      const backendMessages = messagesResponse.data.messages || [];
      
      // Convert backend messages to frontend Message format
      const messages: Message[] = backendMessages.map((bm) => ({
        id: bm.id,
        conversationId: bm.conversation_id || bm.session_id,
        sessionId: bm.session_id || bm.conversation_id,
        senderId: bm.sender_id,
        content: bm.content,
        type: bm.role === 'user' ? 'user' : 'ai',
        messageType: (bm.message_type as any) || 'text',
        role: bm.role,
        timestamp: new Date(bm.created_at),
        threeDCanvas: bm.threeDCanvas,
        pipeline: bm.pipeline,
        attachments: bm.attachments,
        ...(bm.metadata || {}),
      }));
      
      const session: ChatSession = {
        id: sessionData.id,
        title: sessionData.title || 'New Chat',
        createdAt: new Date(sessionData.created_at),
        lastModified: new Date(sessionData.updated_at || sessionData.created_at),
        messages,
        metadata: {
          messageCount: messages.length,
          lastActivity: new Date(sessionData.updated_at || sessionData.created_at),
          starred: false,
          tags: [],
        },
      };
      
      return { session, messages };
    },
    enabled: !!sessionId,
    staleTime: 30 * 1000, // Messages change frequently, cache for 30 seconds
  });
}
