import { AxiosError } from 'axios';
import { useAuthStore } from '../stores/authStore';

/**
 * Global error handler for React Query
 * Handles common HTTP errors and integrates with existing error system
 */
export function handleQueryError(error: unknown): void {
  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const data = error.response?.data;

    switch (status) {
      case 401:
        // Unauthorized - try to refresh token or sign out
        const authStore = useAuthStore.getState();
        if (authStore.refreshToken) {
          // Try to refresh token
          authStore.refreshAccessToken().catch(() => {
            // Refresh failed, sign out
            authStore.signout();
            window.location.href = '/signin';
          });
        } else {
          // No refresh token, sign out immediately
          authStore.signout();
          window.location.href = '/signin';
        }
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
        console.error('[QueryError] Request failed:', status, data);
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
