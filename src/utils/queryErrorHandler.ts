import { AxiosError } from 'axios';

/**
 * Global error handler for React Query
 * Handles common HTTP errors and integrates with existing error system.
 *
 * IMPORTANT: 401 token refresh is handled exclusively by the axios response
 * interceptor in api.ts (with deduplication). Do NOT duplicate that logic here
 * — doing so creates competing refresh attempts that can freeze the browser.
 */
export function handleQueryError(error: unknown): void {
  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const data = error.response?.data;

    switch (status) {
      case 401:
        // Token refresh + redirect is handled by the axios interceptor in api.ts.
        // Nothing to do here — just log for debugging.
        console.warn('[QueryError] 401 Unauthorized (handled by interceptor)');
        break;

      case 402:
        // Payment Required - insufficient credits
        // This will be handled by components showing credit error UI
        console.warn('[QueryError] Payment required - insufficient credits');
        break;

      case 403:
        // Forbidden - user doesn't have permission
        console.warn('[QueryError] Forbidden - insufficient permissions');
        break;

      case 404:
        // Not Found
        console.warn('[QueryError] Resource not found');
        break;

      case 500:
      case 502:
      case 503:
      case 504:
        // Server errors
        console.error('[QueryError] Server error:', status, data);
        break;

      default:
        // Other errors
        if (status) {
          console.error('[QueryError] Request failed:', status, data);
        }
    }
  } else if (error instanceof Error) {
    // Network errors or other errors
    console.error('[QueryError] Error:', error.message);
  } else {
    console.error('[QueryError] Unknown error:', error);
  }
}

/**
 * Check if error should trigger a retry
 */
export function shouldRetryError(error: unknown, _failureCount: number): boolean {
  if (error instanceof AxiosError) {
    const status = error.response?.status;
    
    // Don't retry on client errors (4xx) except 408 (timeout) and 429 (rate limit)
    if (status && status >= 400 && status < 500) {
      return status === 408 || status === 429;
    }
    
    // Retry on server errors (5xx) and network errors
    return status === undefined || (status >= 500 && status < 600);
  }
  
  // Retry on network errors
  return true;
}

/**
 * Calculate retry delay with exponential backoff
 */
export function getRetryDelay(failureCount: number): number {
  return Math.min(1000 * 2 ** failureCount, 30000); // Max 30 seconds
}
