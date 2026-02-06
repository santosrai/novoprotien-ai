/**
 * Job polling utility with exponential backoff and WebSocket support
 */

export interface JobStatus {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'error' | 'cancelled' | 'not_found';
  progress?: number;
  progress_message?: string;
  data?: any;
  error?: string;
  errorCode?: string;
  originalError?: string;
  aiSummary?: string;
  parameters?: Record<string, any>;
}

export interface JobPollerOptions {
  jobId: string;
  jobType: 'alphafold' | 'rfdiffusion';
  onUpdate: (status: JobStatus) => void;
  onComplete: (data: any) => void;
  onError: (error: string) => void;
  enableWebSocket?: boolean;
  maxPollTime?: number; // Maximum polling time in seconds (default: 2 hours)
}

export class JobPoller {
  private jobId: string;
  private jobType: 'alphafold' | 'rfdiffusion';
  private onUpdate: (status: JobStatus) => void;
  private onComplete: (data: any) => void;
  private onError: (error: string) => void;
  private enableWebSocket: boolean;
  private maxPollTime: number;
  
  private pollInterval: number = 3000; // Start with 3 seconds
  private pollTimer?: NodeJS.Timeout;
  private websocket?: WebSocket;
  private startTime: number;
  private isStopped: boolean = false;

  constructor(options: JobPollerOptions) {
    this.jobId = options.jobId;
    this.jobType = options.jobType;
    this.onUpdate = options.onUpdate;
    this.onComplete = options.onComplete;
    this.onError = options.onError;
    this.enableWebSocket = options.enableWebSocket ?? true;
    this.maxPollTime = (options.maxPollTime ?? 7200) * 1000; // Convert to milliseconds
    this.startTime = Date.now();
  }

  start(): void {
    if (this.enableWebSocket) {
      this.connectWebSocket();
    }
    this.startPolling();
  }

  stop(): void {
    this.isStopped = true;
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = undefined;
    }
    if (this.websocket) {
      this.websocket.close();
      this.websocket = undefined;
    }
  }

  private connectWebSocket(): void {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/ws/jobs/${this.jobId}`;
      
      this.websocket = new WebSocket(wsUrl);
      
      this.websocket.onopen = () => {
        console.log(`WebSocket connected for job ${this.jobId}`);
      };
      
      this.websocket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleWebSocketMessage(message);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
      
      this.websocket.onerror = (error) => {
        console.error(`WebSocket error for job ${this.jobId}:`, error);
        // Fallback to polling if WebSocket fails
        if (!this.pollTimer) {
          this.startPolling();
        }
      };
      
      this.websocket.onclose = () => {
        console.log(`WebSocket closed for job ${this.jobId}`);
        // Fallback to polling if WebSocket closes unexpectedly
        if (!this.isStopped && !this.pollTimer) {
          this.startPolling();
        }
      };
    } catch (e) {
      console.warn('WebSocket not available, using polling only:', e);
      // Continue with polling
    }
  }

  private handleWebSocketMessage(message: any): void {
    if (message.type === 'status' || message.type === 'progress') {
      const status: JobStatus = {
        job_id: this.jobId,
        status: message.status || message.data?.status || 'running',
        progress: message.progress ?? message.data?.progress,
        progress_message: message.message ?? message.data?.progress_message,
        data: message.data?.data,
        error: message.error ?? message.data?.error
      };
      
      this.onUpdate(status);
      
      if (status.status === 'completed' && status.data) {
        this.onComplete(status.data);
        this.stop();
      } else if (status.status === 'error') {
        this.onError(status.error || 'Job failed');
        this.stop();
      }
    } else if (message.type === 'completed') {
      this.onComplete(message.data);
      this.stop();
    } else if (message.type === 'error') {
      this.onError(message.error || 'Job failed');
      this.stop();
    }
  }

  private startPolling(): void {
    if (this.isStopped) return;
    
    // Poll immediately
    this.poll();
    
    // Set up interval with exponential backoff
    this.pollTimer = setInterval(() => {
      if (this.isStopped) {
        clearInterval(this.pollTimer!);
        return;
      }
      
      // Check if max time exceeded
      if (Date.now() - this.startTime > this.maxPollTime) {
        this.onError('Job polling timeout exceeded');
        this.stop();
        return;
      }
      
      this.poll();
      this.adjustPollInterval();
    }, this.pollInterval);
  }

  private adjustPollInterval(): void {
    const elapsed = (Date.now() - this.startTime) / 1000; // seconds
    
    if (elapsed < 60) {
      // First minute: 3 seconds
      this.pollInterval = 3000;
    } else if (elapsed < 300) {
      // After 1 minute: 5 seconds
      this.pollInterval = 5000;
    } else if (elapsed < 900) {
      // After 5 minutes: 10 seconds
      this.pollInterval = 10000;
    } else {
      // After 15 minutes: 30 seconds
      this.pollInterval = 30000;
    }
  }

  private async poll(): Promise<void> {
    try {
      const endpoint = this.jobType === 'rfdiffusion' 
        ? `/api/rfdiffusion/status/${this.jobId}`
        : `/api/alphafold/status/${this.jobId}`;
      
      const response = await fetch(endpoint);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const status: JobStatus = await response.json();
      
      this.onUpdate(status);
      
      if (status.status === 'completed' && status.data) {
        this.onComplete(status.data);
        this.stop();
      } else if (status.status === 'error') {
        this.onError(status.error || 'Job failed');
        this.stop();
      }
    } catch (error) {
      console.error(`Failed to poll job ${this.jobId}:`, error);
      // Don't stop on network errors, might be temporary
    }
  }
}
