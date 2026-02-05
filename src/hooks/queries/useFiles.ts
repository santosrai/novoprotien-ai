import { useQuery } from '@tanstack/react-query';
import { api } from '../../utils/api';
import { useAuthStore } from '../../stores/authStore';

export interface FileMetadata {
  file_id: string;
  type: 'upload' | 'rfdiffusion' | 'alphafold' | 'proteinmpnn';
  filename: string;
  size: number;
  job_id?: string;
  download_url: string;
  metadata?: Record<string, any>;
  file_path?: string;
}

interface FilesResponse {
  status: string;
  files: FileMetadata[];
}

/**
 * Query hook for fetching user files
 * Only fetches when user is authenticated
 */
export function useFiles() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  return useQuery<FileMetadata[]>({
    queryKey: ['files'],
    queryFn: async () => {
      const response = await api.get<FilesResponse>('/files');
      if (response.data && response.data.status === 'success') {
        return response.data.files || [];
      }
      return [];
    },
    enabled: isAuthenticated, // Only fetch when authenticated
    staleTime: 1 * 60 * 1000, // Files can change, cache for 1 minute
  });
}

/**
 * Query hook for fetching a single file by ID
 * Only fetches when user is authenticated
 */
export function useFile(fileId: string | null) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  return useQuery<FileMetadata>({
    queryKey: ['files', fileId],
    queryFn: async () => {
      if (!fileId) throw new Error('File ID is required');
      const response = await api.get<{ file: FileMetadata }>(`/files/${fileId}`);
      return response.data.file;
    },
    enabled: isAuthenticated && !!fileId, // Only fetch when authenticated and ID provided
    staleTime: 5 * 60 * 1000, // Single file cache for 5 minutes
  });
}
