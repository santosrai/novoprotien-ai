import { useMemo, useEffect, useRef } from 'react';
import { useStream } from '@langchain/langgraph-sdk/react';
import { createLangGraphTransport, toLangGraphMessages } from '../utils/langgraphTransport';
import { v4 as uuidv4 } from 'uuid';
import { useAppStore } from '../stores/appStore';
import { CodeExecutor } from '../utils/codeExecutor';
import type { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';
import type { ExtendedMessage } from '../types/chat';
import { convertThinkingData } from '../utils/chatHelpers';

export interface UseLangGraphStreamParams {
  rawMessages: any[];
  activeSessionId: string | null;
  isLoading: boolean;
  setIsLoading: (v: boolean) => void;
  addMessage: (msg: any) => void;
  setLastAgentId: (id: string) => void;
  setCurrentCode: (code: string) => void;
  saveVisualizationCode: (sessionId: string, code: string) => void;
  setIsExecuting: (v: boolean) => void;
  setPendingCodeToRun: (code: string) => void;
  setViewerVisibleAndSave: (visible: boolean) => void;
  setActivePane: (pane: 'viewer' | 'editor' | 'files' | 'pipeline' | null) => void;
  routeAction: (responseData: any) => boolean;
}

export function useLangGraphStream({
  rawMessages,
  activeSessionId,
  isLoading,
  setIsLoading,
  addMessage,
  setLastAgentId,
  setCurrentCode,
  saveVisualizationCode,
  setIsExecuting,
  setPendingCodeToRun,
  setViewerVisibleAndSave,
  setActivePane,
  routeAction,
}: UseLangGraphStreamParams) {
  const langGraphTransport = useMemo(() => createLangGraphTransport(), []);
  const langGraphInitialValues = useMemo(
    () => ({ messages: toLangGraphMessages(rawMessages) }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rawMessages.length, activeSessionId]
  );

  const stream = useStream({
    transport: langGraphTransport,
    messagesKey: 'messages',
    initialValues: langGraphInitialValues as { messages: Array<{ type: string; content: string }> },
    threadId: activeSessionId ?? undefined,
    throttle: false,
    onError: (err: unknown) => {
      console.error('[LG stream] onError callback:', err);
      setIsLoading(false);
    },
    onFinish: () => {
      console.log('[LG stream] onFinish callback. stream.values:', stream.values, 'stream.error:', stream.error, 'stream.messages:', stream.messages);
    },
  } as import('@langchain/langgraph-sdk/react').UseStreamCustomOptions<{ messages: Array<{ type: string; content: string }> }>);

  useEffect(() => {
    console.log('[LG stream state]', {
      isLoading: stream.isLoading,
      hasValues: !!stream.values,
      values: stream.values,
      error: stream.error,
      messagesCount: stream.messages?.length ?? 0,
      messages: stream.messages,
    });
  }, [stream.isLoading, stream.values, stream.error, stream.messages]);

  const hasSeenLoadingRef = useRef(false);
  const lastProcessedValuesRef = useRef<unknown>(null);
  useEffect(() => {
    if (stream.isLoading) {
      hasSeenLoadingRef.current = true;
      lastProcessedValuesRef.current = null;
      console.log('[LG stream] isLoading=true, waiting for completion...');
      return;
    }
    if (!hasSeenLoadingRef.current) {
      console.log('[LG stream] isLoading=false but never saw loading=true, skipping (initial render)');
      return;
    }
    hasSeenLoadingRef.current = false;

    const state = stream.values;
    console.log('[LG stream finished]', {
      state,
      activeSessionId,
      isLoading,
      error: stream.error,
      messagesCount: stream.messages?.length ?? 0,
    });

    if (state && activeSessionId) {
      if (lastProcessedValuesRef.current === state) {
        console.log('[LG stream finished] Already processed this state, skipping');
        setIsLoading(false);
        return;
      }
      lastProcessedValuesRef.current = state;

      const appResult = (state as { appResult?: { text?: string; code?: string; agentId?: string; thinkingProcess?: unknown; toolsInvoked?: string[] } })?.appResult;
      const msgs = (state as { messages?: Array<{ type: string; content: string }> })?.messages;
      const lastAi = msgs?.length ? msgs.filter((m) => m.type === 'ai').pop() : null;
      const content = lastAi?.content ?? appResult?.text ?? appResult?.code ?? '';
      console.log('[LG stream finished] from values — content:', content?.slice(0, 100), 'appResult:', appResult);

      const actionHandled = content && routeAction(content);

      const code = appResult?.code ?? '';
      const msgId = uuidv4();
      if (content && !actionHandled) {
        addMessage({
          id: msgId,
          type: 'ai',
          content,
          timestamp: new Date(),
          ...(appResult?.agentId ? { agentId: appResult.agentId } : {}),
          ...(appResult?.toolsInvoked?.length ? { toolsInvoked: appResult.toolsInvoked } : {}),
          ...(appResult?.thinkingProcess ? { thinkingProcess: convertThinkingData(appResult.thinkingProcess) } : {}),
          ...(code && code.trim() && !code.includes('blob:http') && !code.includes('blob:https:')
            ? { threeDCanvas: { id: msgId, sceneData: code } }
            : {}),
        } as ExtendedMessage);
      }
      if (appResult?.agentId) setLastAgentId(appResult.agentId);
      if (code && code.trim()) {
        setCurrentCode(code);
        if (activeSessionId) {
          saveVisualizationCode(activeSessionId, code);
        }
        setViewerVisibleAndSave(true);
        setActivePane('viewer');
        (async () => {
          const currentPlugin = useAppStore.getState().plugin;
          if (currentPlugin) {
            setIsExecuting(true);
            try {
              const exec = new CodeExecutor(currentPlugin as PluginUIContext);
              await exec.executeCode(code);
            } catch (e) {
              console.error('[LG stream] Code execution failed:', e);
            } finally {
              setIsExecuting(false);
            }
          } else {
            setPendingCodeToRun(code);
          }
        })();
      }
      setIsLoading(false);
      return;
    }

    if (activeSessionId && isLoading) {
      const streamMsgs = stream.messages as Array<{ type?: string; content?: unknown }> | undefined;
      const lastAiFromStream = streamMsgs?.length
        ? [...streamMsgs].reverse().find((m) => m.type === 'ai')
        : null;
      const fallbackContent = lastAiFromStream && typeof lastAiFromStream.content === 'string'
        ? lastAiFromStream.content
        : '';
      console.log('[LG stream finished] No values, fallback from stream.messages:', fallbackContent?.slice(0, 100));
      if (fallbackContent) {
        addMessage({
          id: uuidv4(),
          type: 'ai',
          content: fallbackContent,
          timestamp: new Date(),
        } as ExtendedMessage);
      }
    }
    setIsLoading(false);
  }, [stream.isLoading, stream.values, activeSessionId, addMessage, setLastAgentId, setCurrentCode, isLoading, stream.error, stream.messages, saveVisualizationCode, setIsExecuting, setPendingCodeToRun, setViewerVisibleAndSave, setActivePane]);

  useEffect(() => {
    if (stream.error) {
      const errMsg = stream.error instanceof Error ? stream.error.message : String(stream.error);
      console.error('[LG stream error]', errMsg, stream.error);
      if (activeSessionId && isLoading) {
        addMessage({
          id: uuidv4(),
          type: 'ai',
          content: `Something went wrong: ${errMsg}. Please try again.`,
          timestamp: new Date(),
        } as ExtendedMessage);
        setIsLoading(false);
      }
    }
  }, [stream.error, activeSessionId, isLoading, addMessage]);

  useEffect(() => {
    if (!isLoading) return;
    const timer = setTimeout(() => {
      console.warn('[ChatPanel] Loading timeout after 90s — forcing reset');
      setIsLoading(false);
    }, 90_000);
    return () => clearTimeout(timer);
  }, [isLoading]);

  const { messages, hasStreamingContent } = (() => {
    const sessionList = rawMessages as ExtendedMessage[];
    if (stream.isLoading && stream.messages.length > 0) {
      const allStreamMsgs = stream.messages as Array<{ type?: string; content?: unknown; id?: string }>;
      const streamAiMsgs = allStreamMsgs.filter((m) => m.type === 'ai');
      const sessionAiCount = sessionList.filter((m) => m.type === 'ai').length;

      if (streamAiMsgs.length > sessionAiCount) {
        const lastAiMsg = streamAiMsgs[streamAiMsgs.length - 1];
        const streamingContent = typeof lastAiMsg.content === 'string' ? lastAiMsg.content : '';
        if (streamingContent) {
          return {
            messages: [
              ...sessionList,
              { id: 'streaming-ai', content: streamingContent, type: 'ai' as const, timestamp: new Date() } as ExtendedMessage,
            ],
            hasStreamingContent: true,
          };
        }
      }
    }
    return { messages: sessionList, hasStreamingContent: false };
  })();

  return {
    stream,
    messages,
    hasStreamingContent,
  };
}
