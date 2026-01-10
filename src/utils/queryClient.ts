import { QueryClient } from '@tanstack/react-query';
import { handleQueryError, shouldRetryError, getRetryDelay } from './queryErrorHandler';

/**
 * Configured QueryClient for React Query
 * 
 * Configuration:
 * - Default stale time: 5 minutes (moderate caching)
 * - Cache time: 10 minutes
 * - Refetch on window focus: enabled
 * - Retry: 3 attempts with exponential backoff
 * - Global error handler for common HTTP errors
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Data is considered fresh for 5 minutes
      staleTime: 5 * 60 * 1000, // 5 minutes
      
      // Cached data is kept for 10 minutes after it becomes unused
      gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
      
      // Refetch on window focus
      refetchOnWindowFocus: true,
      
      // Retry configuration
      retry: (failureCount, error) => {
        // Max 3 retries
        if (failureCount >= 3) {
          return false;
        }
        // Call error handler before retry
        handleQueryError(error);
        return shouldRetryError(error, failureCount);
      },
      retryDelay: getRetryDelay,
    },
    mutations: {
      // Retry mutations once on network errors
      retry: (failureCount, error) => {
        if (failureCount >= 1) {
          return false;
        }
        // Call error handler before retry
        handleQueryError(error);
        return shouldRetryError(error, failureCount);
      },
      retryDelay: getRetryDelay,
    },
  },
});
