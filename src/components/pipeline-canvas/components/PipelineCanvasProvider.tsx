import React from 'react';
import { PipelineProvider, PipelineProviderProps } from '../context/PipelineContext';

/**
 * PipelineCanvasProvider - Wrapper component for PipelineProvider
 * Provides dependencies to all pipeline canvas components via context
 * 
 * This is the main entry point for dependency injection in the pipeline canvas library.
 * All dependencies are optional, allowing the library to work standalone.
 * 
 * @example
 * ```tsx
 * // Basic usage (no dependencies)
 * <PipelineCanvasProvider>
 *   <PipelineCanvas />
 * </PipelineCanvasProvider>
 * 
 * // With authentication
 * <PipelineCanvasProvider
 *   apiClient={myApiClient}
 *   authState={{ user: currentUser, isAuthenticated: true }}
 *   sessionId={activeSessionId}
 *   getAuthHeaders={() => ({ Authorization: `Bearer ${token}` })}
 * >
 *   <PipelineCanvas />
 * </PipelineCanvasProvider>
 * ```
 */
export const PipelineCanvasProvider: React.FC<PipelineProviderProps> = (props) => {
  return <PipelineProvider {...props} />;
};

// Re-export types for convenience
export type { PipelineProviderProps as PipelineCanvasProviderProps } from '../context/PipelineContext';
