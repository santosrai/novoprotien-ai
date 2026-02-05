/**
 * Dependency injection types for pipeline canvas library
 * These interfaces allow the library to work with any authentication and API system
 */

import { Logger, ErrorReporter } from './logger';

/**
 * User information interface
 * Compatible with most authentication systems
 */
export interface User {
  id: string;
  email?: string;
  name?: string;
  [key: string]: any; // Allow additional user properties
}

/**
 * Authentication state interface
 */
export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  accessToken?: string;
  [key: string]: any; // Allow additional auth properties
}

/**
 * API client interface
 * Compatible with axios, fetch, or custom API clients
 */
export interface ApiClient {
  get: (url: string, config?: { headers?: Record<string, string> }) => Promise<{ data: any }>;
  post: (url: string, data?: any, config?: { headers?: Record<string, string> }) => Promise<{ data: any }>;
  put?: (url: string, data?: any, config?: { headers?: Record<string, string> }) => Promise<{ data: any }>;
  patch?: (url: string, data?: any, config?: { headers?: Record<string, string> }) => Promise<{ data: any }>;
  delete?: (url: string, config?: { headers?: Record<string, string> }) => Promise<{ data: any }>;
}

/**
 * Complete dependencies interface for pipeline canvas
 * All dependencies are optional to allow the library to work standalone
 */
export interface PipelineDependencies {
  /**
   * API client for backend operations (pipeline sync, save, load)
   * If not provided, these operations will be skipped gracefully
   */
  apiClient?: ApiClient;
  
  /**
   * Authentication state
   * If not provided, user-specific features will be disabled
   */
  authState?: AuthState;
  
  /**
   * Active session ID for execution context
   * If not provided, execution will proceed without session tracking
   */
  sessionId?: string;
  
  /**
   * Function to get authentication headers
   * Used for file uploads and authenticated requests
   * If not provided, requests will be made without auth headers
   */
  getAuthHeaders?: () => Record<string, string>;
  
  /**
   * Logger for structured logging
   * If not provided, uses default console logger (development only)
   */
  logger?: Logger;
  
  /**
   * Error reporter for error tracking (Sentry, LogRocket, etc.)
   * If not provided, errors are only logged to console
   */
  errorReporter?: ErrorReporter;
}
