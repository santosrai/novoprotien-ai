/**
 * Logging and error tracking interfaces for pipeline canvas library
 * Allows consumers to integrate with their own logging/error tracking systems
 */

/**
 * Log levels for structured logging
 */
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

/**
 * Logger interface for structured logging
 * Compatible with most logging libraries (winston, pino, console, etc.)
 */
export interface Logger {
  /**
   * Debug-level log (development only, verbose)
   */
  debug: (message: string, data?: Record<string, any>) => void;
  
  /**
   * Info-level log (general information)
   */
  info: (message: string, data?: Record<string, any>) => void;
  
  /**
   * Warning-level log (non-critical issues)
   */
  warn: (message: string, data?: Record<string, any>) => void;
  
  /**
   * Error-level log (errors that don't crash the app)
   */
  error: (message: string, error?: Error, data?: Record<string, any>) => void;
}

/**
 * Error reporter interface for error tracking services
 * Compatible with Sentry, LogRocket, Bugsnag, etc.
 */
export interface ErrorReporter {
  /**
   * Capture an exception/error
   * @param error - The error to capture
   * @param context - Additional context (user, pipeline, node, etc.)
   */
  captureException: (error: Error, context?: Record<string, any>) => void;
  
  /**
   * Capture a message (non-error)
   * @param message - The message to capture
   * @param level - Log level (info, warning, error)
   * @param context - Additional context
   */
  captureMessage: (
    message: string,
    level?: 'info' | 'warning' | 'error',
    context?: Record<string, any>
  ) => void;
  
  /**
   * Set user context (optional, for user-specific error tracking)
   */
  setUser?: (user: { id: string; email?: string; [key: string]: any }) => void;
  
  /**
   * Set additional context (tags, extra data, etc.)
   */
  setContext?: (key: string, context: Record<string, any>) => void;
}

/**
 * Default console logger (used when no logger is provided)
 * Only logs in development mode or when explicitly enabled
 */
export const createDefaultLogger = (enableInProduction = false): Logger => {
  const isDevelopment = typeof window !== 'undefined' && 
    (window.location?.hostname === 'localhost' || 
     window.location?.hostname === '127.0.0.1');
  
  const shouldLog = isDevelopment || enableInProduction;
  
  return {
    debug: (message: string, data?: Record<string, any>) => {
      if (shouldLog) {
        console.debug(`[PipelineCanvas] ${message}`, data || '');
      }
    },
    info: (message: string, data?: Record<string, any>) => {
      if (shouldLog) {
        console.info(`[PipelineCanvas] ${message}`, data || '');
      }
    },
    warn: (message: string, data?: Record<string, any>) => {
      if (shouldLog) {
        console.warn(`[PipelineCanvas] ${message}`, data || '');
      }
    },
    error: (message: string, error?: Error, data?: Record<string, any>) => {
      // Always log errors, but format them nicely
      if (error) {
        console.error(`[PipelineCanvas] ${message}`, error, data || '');
      } else {
        console.error(`[PipelineCanvas] ${message}`, data || '');
      }
    },
  };
};
