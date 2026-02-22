import { useRef, useEffect, useCallback } from 'react';
import type { Message } from '../types/chat';
import { useChatHistoryStore } from '../stores/chatHistoryStore';

export interface UseChatSessionParams {
  activeSessionId: string | null;
  activeSession: { id: string; messages: Message[]; title: string } | null;
  activeSessionMessageCount: number;
  currentCode: string | null;
  isViewerVisible: boolean;
  isSyncing: boolean;
  sessions: Array<{ id: string }>;
  createSession: () => void;
  getVisualizationCode: (sessionId: string) => Promise<string | undefined>;
  getLastCanvasCodeFromSession: (sessionId: string) => string | null | undefined;
  saveVisualizationCode: (sessionId: string, code: string) => void;
  getViewerVisibility: (sessionId: string) => boolean | undefined;
  saveViewerVisibility: (sessionId: string, visible: boolean) => void;
  setCurrentCode: (code: string) => void;
  setViewerVisible: (visible: boolean) => void;
  setActivePane: (pane: 'viewer' | 'editor' | 'files' | 'pipeline' | null) => void;
}

export function useChatSession(params: UseChatSessionParams) {
  const {
    activeSessionId,
    activeSession,
    activeSessionMessageCount,
    currentCode,
    isViewerVisible,
    isSyncing,
    sessions,
    createSession,
    getVisualizationCode,
    getLastCanvasCodeFromSession,
    saveVisualizationCode,
    getViewerVisibility,
    saveViewerVisibility,
    setCurrentCode,
    setViewerVisible,
    setActivePane,
  } = params;

  const previousSessionIdRef = useRef<string | null>(null);
  const currentCodeRef = useRef<string | null>(currentCode);
  const isViewerVisibleRef = useRef<boolean>(isViewerVisible);
  const hasAttemptedCreateRef = useRef<boolean>(false);

  const setViewerVisibleAndSave = useCallback(
    (visible: boolean) => {
      setViewerVisible(visible);
      if (activeSessionId) {
        saveViewerVisibility(activeSessionId, visible);
      }
    },
    [setViewerVisible, activeSessionId, saveViewerVisibility]
  );

  useEffect(() => {
    if (activeSessionId) {
      hasAttemptedCreateRef.current = false;
    }
  }, [activeSessionId]);

  useEffect(() => {
    if (activeSessionId || isSyncing || hasAttemptedCreateRef.current || sessions.length > 0) {
      return;
    }

    const timeoutId = setTimeout(() => {
      const currentState = useChatHistoryStore.getState();
      if (!currentState.activeSessionId && !currentState._isSyncing && currentState.sessions.length === 0) {
        hasAttemptedCreateRef.current = true;
        createSession();
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [activeSessionId, isSyncing, sessions.length, createSession]);

  useEffect(() => {
    if (activeSessionId && !previousSessionIdRef.current) {
      previousSessionIdRef.current = activeSessionId;
      const isNewSession = activeSessionMessageCount < 0 || activeSessionMessageCount === 0;
      if (isNewSession) {
        setViewerVisible(false);
        setActivePane(null);
      } else {
        const savedVisibility = getViewerVisibility(activeSessionId);
        if (savedVisibility !== undefined) {
          setViewerVisible(savedVisibility);
        }
      }
    }
  }, [activeSessionId, activeSessionMessageCount, getViewerVisibility, setViewerVisible, setActivePane]);

  useEffect(() => {
    currentCodeRef.current = currentCode;
  }, [currentCode]);

  useEffect(() => {
    isViewerVisibleRef.current = isViewerVisible;
  }, [isViewerVisible]);

  useEffect(() => {
    if (!activeSessionId) return;

    if (previousSessionIdRef.current && previousSessionIdRef.current !== activeSessionId) {
      const codeToSave = currentCodeRef.current?.trim() || '';
      if (codeToSave) {
        saveVisualizationCode(previousSessionIdRef.current, codeToSave);
        console.log('[ChatPanel] Saved code to previous session:', previousSessionIdRef.current);
      }
      saveViewerVisibility(previousSessionIdRef.current, isViewerVisibleRef.current);
      console.log('[ChatPanel] Saved viewer visibility to previous session:', previousSessionIdRef.current, isViewerVisibleRef.current);
    }

    const isNewSession = !activeSession || activeSession.messages.length === 0;

    if (isNewSession) {
      if (currentCodeRef.current && currentCodeRef.current.trim()) {
        console.log('[ChatPanel] Clearing code for new session:', activeSessionId);
        setCurrentCode('');
      }
      setViewerVisible(false);
      setActivePane(null);
      console.log('[ChatPanel] Hiding all panes for new session:', activeSessionId);
    } else {
      const sessionCode = getLastCanvasCodeFromSession(activeSessionId);
      if (sessionCode) {
        console.log('[ChatPanel] Restoring visualization code from session messages:', activeSessionId);
        setCurrentCode(sessionCode);
        const savedVisibility = getViewerVisibility(activeSessionId);
        setViewerVisible(savedVisibility !== undefined ? savedVisibility : true);
      } else {
        getVisualizationCode(activeSessionId).then((savedCode) => {
          const hasValidCode = savedCode &&
            savedCode.trim() &&
            !savedCode.includes('blob:http://') &&
            !savedCode.includes('blob:https://');

          if (hasValidCode) {
            console.log('[ChatPanel] Restoring visualization code for session:', activeSessionId);
            setCurrentCode(savedCode);
            const savedVisibility = getViewerVisibility(activeSessionId);
            setViewerVisible(savedVisibility !== undefined ? savedVisibility : true);
          } else {
            if (currentCodeRef.current && currentCodeRef.current.trim()) {
              console.log('[ChatPanel] Clearing code for session without valid visualization:', activeSessionId);
              setCurrentCode('');
            }
            setViewerVisible(false);
          }
        }).catch((error) => {
          console.error('[ChatPanel] Failed to restore visualization code:', error);
          setViewerVisible(false);
        });
      }
    }

    previousSessionIdRef.current = activeSessionId;
  }, [activeSessionId, activeSessionMessageCount, getVisualizationCode, getLastCanvasCodeFromSession, saveVisualizationCode, getViewerVisibility, saveViewerVisibility, setCurrentCode, setViewerVisible]);

  return { setViewerVisibleAndSave };
}
