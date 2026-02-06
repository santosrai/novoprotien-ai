import React, { useState, useEffect } from 'react';
import { X, Clock } from 'lucide-react';
import { Message } from '../stores/chatHistoryStore';
import { useJobStatus } from '../hooks/queries/useJobStatus';
import { useAlphaFoldCancel,  } from '../hooks/mutations/useAlphaFold';
import { useRFdiffusionCancel as useRFdiffusionCancelHook } from '../hooks/mutations/useRFdiffusion';

export interface JobErrorData {
  error: string;
  errorCode?: string;
  originalError?: string;
  aiSummary?: string;
  parameters?: Record<string, any>;
}

interface JobLoadingPillProps {
  message: Message;
  onJobComplete: (pdbData: any) => void;
  onJobError: (error: string, errorData?: JobErrorData) => void;
  onCancel?: () => void;
}

export const JobLoadingPill: React.FC<JobLoadingPillProps> = ({
  message,
  onJobComplete,
  onJobError,
  onCancel
}) => {
  const jobType = (message.jobType === 'proteinmpnn' ? 'alphafold' : message.jobType) || 'alphafold';
  const { data: jobStatus, error: jobError } = useJobStatus(
    message.jobId || null,
    jobType as 'alphafold' | 'rfdiffusion' | 'proteinmpnn',
    {
      enabled: !!message.jobId,
      refetchInterval: 3000,
      maxPollTime: 2 * 60 * 60 * 1000, // 2 hours
    }
  );
  
  const cancelAlphaFold = useAlphaFoldCancel();
  const cancelRFdiffusion = useRFdiffusionCancelHook();
  
  const [elapsedTime, setElapsedTime] = useState(0);
  const [startTime] = useState(Date.now());

  // Update progress and status from job status
  const progress = jobStatus?.progress || 0;
  const progressMessage = jobStatus?.progress_message || '';
  const status = jobStatus?.status === 'completed' ? 'completed' 
    : jobStatus?.status === 'error' ? 'error'
    : jobStatus?.status === 'not_found' ? 'error' // Treat not_found as error (job lost after restart)
    : 'running';

  // Handle job completion
  useEffect(() => {
    if (jobStatus?.status === 'completed' && jobStatus.data) {
      onJobComplete(jobStatus.data);
    }
  }, [jobStatus?.status, jobStatus?.data, onJobComplete]);

  // Handle job error
  useEffect(() => {
    if (jobStatus?.status === 'error' || jobStatus?.status === 'not_found' || jobError) {
      const errorMessage = jobStatus?.status === 'not_found' 
        ? 'Job not found. The server may have been restarted. Please try submitting the job again.'
        : jobStatus?.error || jobError?.message || 'Job failed';
      
      // Pass full error data including AI summary from server
      const errorData: JobErrorData = {
        error: errorMessage,
        errorCode: jobStatus?.errorCode,
        originalError: jobStatus?.originalError,
        aiSummary: jobStatus?.aiSummary,
        parameters: jobStatus?.parameters,
      };
      onJobError(errorMessage, errorData);
    }
  }, [jobStatus?.status, jobStatus?.error, jobStatus?.aiSummary, jobError, onJobError]);

  // Elapsed time counter
  useEffect(() => {
    if (status !== 'running') return;
    
    const timer = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    
    return () => clearInterval(timer);
  }, [status, startTime]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getJobDisplayName = () => {
    return message.jobType === 'rfdiffusion' ? 'Protein Design' : 'Protein Folding';
  };

  const getEstimatedTime = () => {
    return message.jobType === 'rfdiffusion' ? '2-8 min' : '2-5 min';
  };

  const handleCancel = async () => {
    if (!message.jobId) return;
    
    try {
      if (message.jobType === 'rfdiffusion') {
        await cancelRFdiffusion.mutateAsync(message.jobId);
      } else {
        await cancelAlphaFold.mutateAsync(message.jobId);
      }
      
      onCancel?.();
    } catch (error) {
      console.error('Failed to cancel job:', error);
    }
  };

  if (status === 'completed') {
    return null; // Don't show pill when completed, PDB data will be shown instead
  }

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 my-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          {/* Animated Icon */}
          <div className="relative">
            {message.jobType === 'rfdiffusion' ? (
              <div className="w-6 h-6 text-blue-600 animate-spin">🧬</div>
            ) : (
              <div className="w-6 h-6 text-blue-600 animate-pulse">🔬</div>
            )}
          </div>
          
          {/* Status and Progress */}
          <div className="flex-1">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-blue-800">
                {getJobDisplayName()} in progress...
              </span>
              <div className="flex space-x-1">
                <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"></div>
                <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
            
            {/* Progress Bar */}
            <div className="mt-2 flex items-center space-x-2">
              <div className="flex-1 bg-blue-100 rounded-full h-2">
                <div 
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
              <span className="text-xs text-blue-600 font-mono min-w-[3rem]">
                {Math.round(progress)}%
              </span>
            </div>
            
            {/* Progress Message */}
            {progressMessage && (
              <div className="mt-1 text-xs text-blue-600 italic">
                {progressMessage}
              </div>
            )}
            
            {/* Time Info */}
            <div className="mt-1 flex items-center space-x-4 text-xs text-blue-600">
              <div className="flex items-center space-x-1">
                <Clock className="w-3 h-3" />
                <span>Elapsed: {formatTime(elapsedTime)}</span>
              </div>
              <span>Est. {getEstimatedTime()}</span>
              <span>Job: {message.jobId?.slice(-6)}</span>
            </div>
          </div>
        </div>
        
        {/* Cancel Button */}
        {onCancel && (
          <button
            onClick={handleCancel}
            className="p-1 hover:bg-blue-100 rounded-full transition-colors"
            title="Cancel job"
          >
            <X className="w-4 h-4 text-blue-600" />
          </button>
        )}
      </div>
      
      {/* Status Messages */}
      {status === 'error' && (
        <div className="mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded p-2">
          Job failed or was cancelled
        </div>
      )}
    </div>
  );
};