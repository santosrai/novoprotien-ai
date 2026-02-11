/**
 * Adapter interfaces for backend abstraction
 * Allows the pipeline-canvas library to work with any backend framework
 */

import { Pipeline } from './index';
import { ApiClient } from './dependencies';

/**
 * Options for saving a pipeline
 */
export interface SaveOptions {
  /**
   * Optional message ID to link the pipeline to a message
   */
  messageId?: string;
  /**
   * Optional conversation ID to link the pipeline to a conversation
   */
  conversationId?: string;
  /**
   * Optional session ID (used as conversation ID if conversationId not provided)
   */
  sessionId?: string;
  /**
   * Pipeline status (default: 'draft')
   */
  status?: 'draft' | 'running' | 'completed' | 'failed';
}

/**
 * Filters for listing pipelines
 */
export interface ListFilters {
  /**
   * Filter by status
   */
  status?: 'draft' | 'running' | 'completed' | 'failed';
  /**
   * Filter by message ID
   */
  messageId?: string;
  /**
   * Filter by conversation ID
   */
  conversationId?: string;
  /**
   * Limit number of results
   */
  limit?: number;
  /**
   * Offset for pagination
   */
  offset?: number;
  /**
   * When true, request full pipeline data (nodes, edges) in list response.
   * Avoids N+1 fetches when syncing.
   */
  full?: boolean;
}

/**
 * Pipeline Persistence Adapter
 * Handles saving, loading, listing, and deleting pipelines
 */
export interface PipelinePersistenceAdapter {
  /**
   * Save a pipeline to the backend
   * @param pipeline The pipeline to save
   * @param options Optional save options
   * @returns Promise resolving to the saved pipeline ID
   */
  save(pipeline: Pipeline, options?: SaveOptions): Promise<{ id: string }>;

  /**
   * Load a pipeline by ID
   * @param id The pipeline ID
   * @returns Promise resolving to the pipeline
   */
  load(id: string): Promise<Pipeline>;

  /**
   * List pipelines with optional filters
   * @param filters Optional filters for listing
   * @returns Promise resolving to an array of pipelines
   */
  list(filters?: ListFilters): Promise<Pipeline[]>;

  /**
   * Delete a pipeline by ID
   * @param id The pipeline ID
   * @returns Promise that resolves when deletion is complete
   */
  delete(id: string): Promise<void>;

  /**
   * Optional: Sync pipelines from backend
   * Used for initial load and periodic synchronization
   * @returns Promise resolving to an array of pipelines
   */
  sync?(): Promise<Pipeline[]>;
}

/**
 * Node execution parameters
 */
export interface NodeExecutionParams {
  /**
   * Node type (e.g., 'rfdiffusion_node', 'alphafold_node')
   */
  nodeType: string;
  /**
   * Node configuration
   */
  config: Record<string, any>;
  /**
   * Input data from connected nodes
   */
  inputData: Record<string, any>;
  /**
   * Optional session ID for execution context
   */
  sessionId?: string;
}

/**
 * Node Execution Adapter
 * Handles execution of individual pipeline nodes
 */
export interface NodeExecutionAdapter {
  /**
   * Execute a node with given parameters
   * @param params Node execution parameters
   * @returns Promise resolving to the execution result
   */
  execute(params: NodeExecutionParams): Promise<any>;

  /**
   * Optional: Check execution status for async operations
   * @param jobId Job ID returned from execute()
   * @returns Promise resolving to execution status and result if complete
   */
  checkStatus?(jobId: string): Promise<{ status: 'running' | 'completed' | 'failed'; result?: any; error?: string }>;

  /**
   * Optional: Cancel a running execution
   * @param jobId Job ID to cancel
   * @returns Promise that resolves when cancellation is complete
   */
  cancel?(jobId: string): Promise<void>;
}

/** Options for NovoProteinAdapter */
export interface NovoProteinAdapterOptions {
  /** Session ID for no-auth mode; sent as X-Session-Id header */
  sessionId?: string;
}

/**
 * Default NovoProtein Adapter Implementation
 * Implements the adapter interfaces using NovoProtein's current API structure
 */
export class NovoProteinAdapter implements PipelinePersistenceAdapter {
  private readonly sessionId?: string;
  constructor(
    private apiClient: ApiClient,
    options?: NovoProteinAdapterOptions
  ) {
    if (!apiClient) {
      throw new Error('ApiClient is required for NovoProteinAdapter');
    }
    this.sessionId = options?.sessionId;
  }

  private getHeaders(extra?: Record<string, string>): Record<string, string> {
    const headers: Record<string, string> = { ...extra };
    if (this.sessionId) {
      headers['X-Session-Id'] = this.sessionId;
    }
    return headers;
  }

  async save(pipeline: Pipeline, options?: SaveOptions): Promise<{ id: string }> {
    const pipelineData: any = { ...pipeline };
    
    if (options?.messageId) {
      pipelineData.message_id = options.messageId;
    }
    if (options?.conversationId) {
      pipelineData.conversation_id = options.conversationId;
    } else if (!options?.conversationId && options?.messageId && options?.sessionId) {
      pipelineData.conversation_id = options.sessionId;
    }
    if (options?.status) {
      pipelineData.status = options.status;
    }

    const response = await this.apiClient.post('/pipelines', pipelineData, {
      headers: this.getHeaders(),
    });
    
    // Handle NovoProtein response format: { status: "success", pipeline: {...} }
    if (response.data?.pipeline?.id) {
      return { id: response.data.pipeline.id };
    }
    if (response.data?.id) {
      return { id: response.data.id };
    }
    
    // Fallback: use pipeline's existing ID
    return { id: pipeline.id };
  }

  async load(id: string): Promise<Pipeline> {
    const response = await this.apiClient.get(`/pipelines/${id}`, {
      headers: this.getHeaders(),
    });
    
    // Handle NovoProtein response format
    const backendPipeline = response.data?.pipeline || response.data;
    
    // Convert date strings to Date objects
    if (backendPipeline.createdAt && typeof backendPipeline.createdAt === 'string') {
      backendPipeline.createdAt = new Date(backendPipeline.createdAt);
    }
    if (backendPipeline.updatedAt && typeof backendPipeline.updatedAt === 'string') {
      backendPipeline.updatedAt = new Date(backendPipeline.updatedAt);
    }
    
    return backendPipeline;
  }

  async list(filters?: ListFilters): Promise<Pipeline[]> {
    const searchParams = new URLSearchParams();
    if (filters?.conversationId) searchParams.set('conversation_id', filters.conversationId);
    if (filters?.full) searchParams.set('full', 'true');
    const query = searchParams.toString();
    const url = query ? `/pipelines?${query}` : '/pipelines';

    const response = await this.apiClient.get(url, {
      headers: this.getHeaders(),
    });

    // Handle NovoProtein response format: { pipelines: [...] }
    let backendPipelines = response.data?.pipelines || response.data || [];

    // Apply filters if provided
    if (filters?.status) {
      backendPipelines = backendPipelines.filter((p: any) => p.status === filters.status);
    }
    if (filters?.messageId) {
      backendPipelines = backendPipelines.filter((p: any) => p.message_id === filters.messageId);
    }

    // Convert date strings to Date objects (handle both created_at and createdAt)
    return backendPipelines.map((p: any) => {
      const createdAt = p.createdAt ?? p.created_at;
      const updatedAt = p.updatedAt ?? p.updated_at;
      const result = { ...p };
      result.createdAt = createdAt
        ? (typeof createdAt === 'string' ? new Date(createdAt) : createdAt)
        : (p.createdAt ?? new Date());
      result.updatedAt = updatedAt
        ? (typeof updatedAt === 'string' ? new Date(updatedAt) : updatedAt)
        : (p.updatedAt ?? new Date());
      return result;
    });
  }

  async delete(id: string): Promise<void> {
    const headers = this.getHeaders();
    if (this.apiClient.delete) {
      await this.apiClient.delete(`/pipelines/${id}`, { headers });
    } else {
      // Fallback: use POST with method override
      await this.apiClient.post(`/pipelines/${id}`, {}, { 
        headers: { ...headers, 'X-HTTP-Method-Override': 'DELETE' } 
      });
    }
  }

  async sync(): Promise<Pipeline[]> {
    // Use full=true to get all pipeline data in one request (avoids N+1)
    const pipelines = await this.list({ full: true });

    // If backend returned summaries (no nodes), fall back to per-pipeline loads
    const needsFullLoad = pipelines.some((p: any) => !p.nodes && !p.edges);
    if (needsFullLoad) {
      return Promise.all(
        pipelines.map(async (p) => {
          try {
            return await this.load(p.id);
          } catch (error) {
            console.error(`Failed to load full pipeline ${p.id}:`, error);
            return p;
          }
        })
      );
    }

    return pipelines;
  }
}
