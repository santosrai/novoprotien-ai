/**
 * Logging utilities for pipeline canvas library
 * Provides helper functions to use logger from context with fallback
 */

import { Logger, ErrorReporter, createDefaultLogger } from '../types/logger';

let defaultLogger: Logger | null = null;

/**
 * Get logger from context or use default
 * Creates default logger on first use
 */
export const getLogger = (logger?: Logger): Logger => {
  if (logger) {
    return logger;
  }
  
  if (!defaultLogger) {
    defaultLogger = createDefaultLogger();
  }
  
  return defaultLogger;
};

/**
 * Get error reporter from context
 */
export const getErrorReporter = (errorReporter?: ErrorReporter): ErrorReporter | undefined => {
  return errorReporter;
};

/**
 * Log error with error reporter if available
 */
export const logError = (
  message: string,
  error: Error,
  context: Record<string, any> = {},
  logger?: Logger,
  errorReporter?: ErrorReporter
) => {
  const effectiveLogger = getLogger(logger);
  effectiveLogger.error(message, error, context);
  
  if (errorReporter) {
    errorReporter.captureException(error, {
      message,
      ...context,
    });
  }
};

/**
 * Log message with error reporter if available
 */
export const logMessage = (
  message: string,
  level: 'info' | 'warning' | 'error' = 'info',
  context: Record<string, any> = {},
  logger?: Logger,
  errorReporter?: ErrorReporter
) => {
  const effectiveLogger = getLogger(logger);
  
  switch (level) {
    case 'info':
      effectiveLogger.info(message, context);
      break;
    case 'warning':
      effectiveLogger.warn(message, context);
      break;
    case 'error':
      effectiveLogger.error(message, undefined, context);
      break;
  }
  
  if (errorReporter && level !== 'info') {
    errorReporter.captureMessage(message, level, context);
  }
};
