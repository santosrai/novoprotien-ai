import React, { useState, useEffect } from 'react';
import { Clock, CheckCircle, XCircle, Loader2, Download, Filter } from 'lucide-react';
import { api } from '../utils/api';

interface AlphaFoldJob {
  id: string;
  user_id: string;
  session_id?: string;
  sequence: string;
  sequence_length: number;
  parameters: any;
  status: 'queued' | 'running' | 'completed' | 'error' | 'cancelled';
  nvidia_req_id?: string;
  result_filepath?: string;
  error_message?: string;
  progress: number;
  progress_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  updated_at: string;
}

interface JobHistoryProps {
  onJobSelect?: (job: AlphaFoldJob) => void;
}

export const JobHistory: React.FC<JobHistoryProps> = ({ onJobSelect }) => {
  const [jobs, setJobs] = useState<AlphaFoldJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadJobs();
  }, [statusFilter]);

  const loadJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params: any = { limit: 50 };
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      
      const response = await api.get('/jobs/alphafold', { params });
      setJobs(response.data.jobs || []);
    } catch (err: any) {
      console.error('Failed to load job history:', err);
      setError(err.response?.data?.detail || 'Failed to load job history');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const formatDuration = (start?: string, end?: string) => {
    if (!start) return 'N/A';
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const seconds = Math.floor((endTime - startTime) / 1000);
    
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
      case 'cancelled':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'running':
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'queued':
        return <Clock className="w-5 h-5 text-yellow-500" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'error':
      case 'cancelled':
        return 'bg-red-100 text-red-800';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'queued':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const handleDownload = async (job: AlphaFoldJob) => {
    if (!job.result_filepath) return;
    
    try {
      // Construct download URL
      const fileId = job.id;
      const response = await api.get(`/files/${fileId}/download`, {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `alphafold_${job.id}.pdb`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download file:', err);
      alert('Failed to download file');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        <span className="ml-2 text-gray-600">Loading job history...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-red-800">{error}</p>
        <button
          onClick={loadJobs}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex items-center space-x-4">
        <Filter className="w-5 h-5 text-gray-500" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Status</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="error">Error</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <button
          onClick={loadJobs}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>

      {/* Job List */}
      {jobs.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          No jobs found
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer transition-colors"
              onClick={() => onJobSelect?.(job)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-3">
                    {getStatusIcon(job.status)}
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-gray-900">
                          Job {job.id.slice(-8)}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(job.status)}`}>
                          {job.status}
                        </span>
                      </div>
                      <div className="mt-1 text-sm text-gray-600">
                        Sequence length: {job.sequence_length} residues
                      </div>
                    </div>
                  </div>

                  {job.status === 'running' && (
                    <div className="mt-2">
                      <div className="flex items-center space-x-2">
                        <div className="flex-1 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full transition-all"
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-600">{Math.round(job.progress)}%</span>
                      </div>
                      {job.progress_message && (
                        <div className="mt-1 text-xs text-gray-500 italic">
                          {job.progress_message}
                        </div>
                      )}
                    </div>
                  )}

                  <div className="mt-2 flex items-center space-x-4 text-xs text-gray-500">
                    <div className="flex items-center space-x-1">
                      <Clock className="w-3 h-3" />
                      <span>Created: {formatDate(job.created_at)}</span>
                    </div>
                    {job.started_at && (
                      <span>Started: {formatDate(job.started_at)}</span>
                    )}
                    {job.completed_at && (
                      <span>Completed: {formatDate(job.completed_at)}</span>
                    )}
                    <span>Duration: {formatDuration(job.started_at, job.completed_at)}</span>
                  </div>

                  {job.error_message && (
                    <div className="mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded p-2">
                      {job.error_message}
                    </div>
                  )}
                </div>

                {job.status === 'completed' && job.result_filepath && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDownload(job);
                    }}
                    className="ml-4 p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    title="Download result"
                  >
                    <Download className="w-5 h-5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
