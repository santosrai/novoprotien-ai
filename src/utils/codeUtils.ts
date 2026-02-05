import { useAppStore } from '../stores/appStore';
import { useChatHistoryStore } from '../stores/chatHistoryStore';

/**
 * Checks if code is valid visualization code
 */
const isValidVisualizationCode = (code: string | null | undefined): boolean => {
  if (!code || !code.trim()) return false;
  if (code.includes('blob:http://') || code.includes('blob:https://')) {
    return false; // Filter out blob URLs (they expire)
  }
  return true;
};

/**
 * Gets code from all sources (prioritizes newest)
 */
export const getCodeToExecute = (
  currentCode: string,
  pendingCodeToRun: string | null,
  activeSessionId: string | null,
  getActiveSession: () => any
): string | null => {
  // Priority 1: Pending code (highest priority - queued for execution)
  if (isValidVisualizationCode(pendingCodeToRun)) {
    return pendingCodeToRun;
  }
  
  // Priority 2: Latest AI message code
  if (activeSessionId) {
    const activeSession = getActiveSession();
    const lastAiMessageWithCode = activeSession?.messages
      ?.filter((m: any) => m.type === 'ai' && m.threeDCanvas?.sceneData)
      ?.sort((a: any, b: any) => {
        const aTime = a.timestamp instanceof Date ? a.timestamp.getTime() : new Date(a.timestamp).getTime();
        const bTime = b.timestamp instanceof Date ? b.timestamp.getTime() : new Date(b.timestamp).getTime();
        return bTime - aTime;
      })?.[0];
    
    if (lastAiMessageWithCode?.threeDCanvas?.sceneData) {
      const code = lastAiMessageWithCode.threeDCanvas.sceneData;
      if (isValidVisualizationCode(code)) {
        return code;
      }
    }
  }
  
  // Priority 3: Global currentCode
  if (isValidVisualizationCode(currentCode)) {
    return currentCode;
  }
  
  return null;
};

/**
 * Hook to check if visualization code exists
 */
export const useHasCode = (): boolean => {
  const { currentCode, pendingCodeToRun } = useAppStore();
  const { activeSessionId, getActiveSession } = useChatHistoryStore();
  
  const code = getCodeToExecute(
    currentCode,
    pendingCodeToRun,
    activeSessionId,
    getActiveSession
  );
  
  return code !== null;
};
