import { useMutation, useQueryClient } from '@tanstack/react-query';
import { getAuthHeaders } from '../../utils/api';

interface FileUploadResponse {
  status: string;
  file_info: {
    file_id: string;
    filename: string;
    file_url: string;
    atoms?: number;
    chains?: string[];
    chain_residue_counts?: Record<string, number>;
    total_residues?: number;
    suggested_contigs?: string;
    size?: number;
  };
}

interface FileUploadParams {
  file: File;
  sessionId?: string;
}

/**
 * Mutation hook for uploading PDB files
 */
export function useFileUpload() {
  const queryClient = useQueryClient();
  
  return useMutation<FileUploadResponse, Error, FileUploadParams>({
    mutationFn: async ({ file, sessionId }) => {
      const formData = new FormData();
      formData.append('file', file);
      if (sessionId) {
        formData.append('session_id', sessionId);
      }
      
      const headers = getAuthHeaders();
      
      const response = await fetch('/api/upload/pdb', {
        method: 'POST',
        headers,
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || 'Upload failed');
      }
      
      return await response.json();
    },
    onSuccess: () => {
      // Invalidate files query to refresh file list
      queryClient.invalidateQueries({ queryKey: ['files'] });
      
      // Dispatch event for other components
      window.dispatchEvent(new CustomEvent('session-file-added'));
    },
  });
}

/**
 * Mutation hook for deleting files
 */
export function useFileDelete() {
  const queryClient = useQueryClient();
  
  return useMutation<void, Error, string>({
    mutationFn: async (fileId) => {
      const headers = getAuthHeaders();
      
      const response = await fetch(`/api/files/${fileId}`, {
        method: 'DELETE',
        headers,
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Delete failed' }));
        throw new Error(errorData.detail || 'Delete failed');
      }
    },
    onSuccess: () => {
      // Invalidate files query to refresh file list
      queryClient.invalidateQueries({ queryKey: ['files'] });
      
      // Dispatch event for other components
      window.dispatchEvent(new CustomEvent('session-file-deleted'));
    },
  });
}
