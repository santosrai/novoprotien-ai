import { useMemo } from 'react';
import { NodeStatus } from '../types/index';

/**
 * Determines if a node is completed based on status or result metadata
 */
export const useNodeCompletionStatus = (data: {
  status?: NodeStatus;
  result_metadata?: Record<string, any>;
  error?: string;
}): boolean => {
  return useMemo(() => {
    const status = data.status;
    // Error nodes are never "completed" - they represent failure
    // Check both status and error (error can persist when status is reset)
    if (status === 'error' || data.error) return false;
    return !!(
      status === 'completed' ||
      status === 'success' ||
      (data.result_metadata && Object.keys(data.result_metadata).length > 0)
    );
  }, [data.status, data.result_metadata, data.error]);
};
