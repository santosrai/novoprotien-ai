/**
 * LangGraph SDK transport for NovoProtein FastAPI streaming endpoint.
 * Connects useStream to POST /api/agents/route/stream/sse (SSE) with auth.
 */

import { FetchStreamTransport } from '@langchain/langgraph-sdk/react';
import { getAuthHeaders } from './api';

// Use relative URL so the Vite dev proxy forwards to the backend;
// in production, VITE_API_BASE can be set to the absolute URL.
const VITE_API_BASE = (import.meta as any)?.env?.VITE_API_BASE || '/api';
const streamSseUrl = `${VITE_API_BASE}/agents/route/stream/sse`;

export interface LangGraphState extends Record<string, unknown> {
  messages: Array<{ type: string; content: string }>;
  appResult?: {
    agentId?: string;
    text?: string;
    code?: string;
    reason?: string;
    type?: string;
    thinkingProcess?: unknown;
    toolsInvoked?: string[];
    toolResults?: Array<{
      name?: string;
      result?: {
        content?: string;
        filename?: string;
        error?: string;
      };
    }>;
    tokenUsage?: {
      inputTokens: number;
      outputTokens: number;
      totalTokens: number;
    };
  };
}

/**
 * Transport for useStream that POSTs to our FastAPI SSE endpoint.
 * Pass to useStream({ transport: createLangGraphTransport() }).
 */
export function createLangGraphTransport(): FetchStreamTransport<LangGraphState> {
  return new FetchStreamTransport({
    apiUrl: streamSseUrl,
    defaultHeaders: getAuthHeaders() as HeadersInit,
    onRequest: async (_url, init) => {
      const headers = new Headers(init.headers);
      const auth = getAuthHeaders();
      Object.entries(auth).forEach(([k, v]) => headers.set(k, v));
      console.log('[LG Transport] POST', streamSseUrl);
      return { ...init, headers };
    },
    // Custom fetch: log response status & tee body to log SSE events for debugging
    fetch: async (...args: Parameters<typeof globalThis.fetch>) => {
      const resp = await globalThis.fetch(...args);
      console.log('[LG Transport] response', resp.status, resp.statusText, 'type:', resp.headers.get('content-type'));
      if (!resp.ok || !resp.body) return resp;
      // Tee the body so we can log SSE events without consuming the stream
      const [forSDK, forLog] = resp.body.tee();
      // Fire-and-forget reader for debug logging
      (async () => {
        const reader = forLog.getReader();
        const dec = new TextDecoder();
        let count = 0;
        try {
          // eslint-disable-next-line no-constant-condition
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const text = dec.decode(value, { stream: true });
            count++;
            console.log(`[LG Transport] SSE chunk #${count}:`, text.slice(0, 300));
          }
          console.log(`[LG Transport] stream done, ${count} chunks`);
        } catch (e) { console.warn('[LG Transport] log reader err', e); }
      })();
      return new Response(forSDK, { status: resp.status, statusText: resp.statusText, headers: resp.headers });
    },
  } as ConstructorParameters<typeof FetchStreamTransport>[0]);
}

/** Convert store messages to LangGraph format for initialValues / submit. */
export function toLangGraphMessages(
  messages: Array<{ type: string; content: string }>
): Array<{ type: 'human' | 'ai'; content: string }> {
  return messages.map((m) => ({
    type: (m.type === 'user' ? 'human' : 'ai') as 'human' | 'ai',
    content: typeof m.content === 'string' ? m.content : '',
  }));
}
