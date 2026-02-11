import React, { createContext, useContext, ReactNode, useEffect, useMemo } from 'react';
import { PipelineDependencies } from '../types/dependencies';
import { PipelinePersistenceAdapter, NodeExecutionAdapter } from '../types/adapters';
import { PipelineConfig } from '../types/config';
import { setPipelineDependencies, setPipelineAdapters, setPipelineConfig } from '../store/pipelineStore';

const SESSION_STORAGE_KEY = 'pipeline-canvas-session-id';

/** Get or create session ID for no-auth mode (persisted in sessionStorage) */
function getOrCreateSessionId(): string {
  if (typeof sessionStorage === 'undefined') return `anon-${Date.now()}`;
  let id = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (!id) {
    id = `sess-${crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)}`;
    sessionStorage.setItem(SESSION_STORAGE_KEY, id);
  }
  return id;
}

/**
 * Pipeline Context Value
 * All dependencies are optional to allow standalone usage
 */
interface PipelineContextValue extends PipelineDependencies {
  /**
   * Optional pipeline persistence adapter
   */
  persistenceAdapter?: PipelinePersistenceAdapter;
  /**
   * Optional node execution adapter
   */
  executionAdapter?: NodeExecutionAdapter;
  /**
   * Optional pipeline configuration
   */
  config?: PipelineConfig;
}

/**
 * Pipeline Context
 * Provides dependencies to all pipeline canvas components
 */
const PipelineContext = createContext<PipelineContextValue | undefined>(undefined);

/**
 * Pipeline Provider Props
 */
export interface PipelineProviderProps {
  children: ReactNode;
  /**
   * Optional API client for backend operations
   */
  apiClient?: PipelineDependencies['apiClient'];
  /**
   * Optional authentication state
   */
  authState?: PipelineDependencies['authState'];
  /**
   * Optional session ID for execution context
   */
  sessionId?: PipelineDependencies['sessionId'];
  /**
   * Optional function to get authentication headers
   */
  getAuthHeaders?: PipelineDependencies['getAuthHeaders'];
  /**
   * Optional logger for structured logging
   */
  logger?: PipelineDependencies['logger'];
  /**
   * Optional error reporter for error tracking
   */
  errorReporter?: PipelineDependencies['errorReporter'];
  /**
   * Optional pipeline persistence adapter
   * If not provided, will use default adapter with apiClient
   */
  persistenceAdapter?: PipelinePersistenceAdapter;
  /**
   * Optional node execution adapter
   * If not provided, will use default execution engine
   */
  executionAdapter?: NodeExecutionAdapter;
  /**
   * Optional pipeline configuration
   * Allows customization of endpoints and response transformers
   */
  config?: PipelineConfig;
}

/**
 * Pipeline Provider Component
 * Wraps the pipeline canvas components and provides dependencies via context
 */
export const PipelineProvider: React.FC<PipelineProviderProps> = ({
  children,
  apiClient,
  authState,
  sessionId: sessionIdProp,
  getAuthHeaders,
  logger,
  errorReporter,
  persistenceAdapter,
  executionAdapter,
  config,
}) => {
  // Auto-generate sessionId for no-auth mode when not provided
  const sessionId = useMemo(() => {
    if (sessionIdProp) return sessionIdProp;
    if (config?.features?.useBackendWithoutAuth && apiClient) {
      return getOrCreateSessionId();
    }
    return undefined;
  }, [sessionIdProp, config?.features?.useBackendWithoutAuth, apiClient]);

  const value: PipelineContextValue = {
    apiClient,
    authState,
    sessionId,
    getAuthHeaders,
    logger,
    errorReporter,
    persistenceAdapter,
    executionAdapter,
    config,
  };

  // Update store dependencies when context changes (no auto-sync on mount)
  useEffect(() => {
    setPipelineDependencies({
      apiClient,
      authState,
      sessionId,
    });
    
    // Set adapters if provided
    if (persistenceAdapter || executionAdapter) {
      setPipelineAdapters({
        persistence: persistenceAdapter,
        execution: executionAdapter,
      });
    }
    
    // Set configuration if provided
    if (config) {
      setPipelineConfig(config);
    }
    // Pipelines are not synced on mount - use persisted state on load.
    // Sync happens after sign-in (authStore) or when user clicks Refresh in pipeline sidebar.
  }, [apiClient, authState, sessionId, persistenceAdapter, executionAdapter, config]);

  return (
    <PipelineContext.Provider value={value}>
      {children}
    </PipelineContext.Provider>
  );
};

/**
 * Hook to access pipeline context
 * Returns undefined if used outside of PipelineProvider
 */
export const usePipelineContext = (): PipelineContextValue => {
  const context = useContext(PipelineContext);
  
  // Return empty object if context is not available (allows standalone usage)
  if (context === undefined) {
    return {};
  }
  
  return context;
};
