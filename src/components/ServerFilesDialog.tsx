import React from 'react';
import { X, Folder } from 'lucide-react';
import { FileBrowser } from './FileBrowser';
import { getAuthHeaders } from '../utils/api';

interface FileMetadata {
  file_id: string;
  type: 'upload' | 'rfdiffusion' | 'alphafold' | 'proteinmpnn';
  filename: string;
  size: number;
  job_id?: string;
  download_url: string;
  metadata?: Record<string, any>;
}

interface ServerFilesDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onFileSelect: (file: File) => void;
  onError: (error: string) => void;
}

export const ServerFilesDialog: React.FC<ServerFilesDialogProps> = ({
  isOpen,
  onClose,
  onFileSelect,
  onError,
}) => {
  if (!isOpen) return null;

  const handleFileSelect = async (fileMetadata: FileMetadata) => {
    try {
      // Fetch file content with authentication headers
      const headers = getAuthHeaders();
      const fileResponse = await fetch(fileMetadata.download_url, { headers });
      
      if (!fileResponse.ok) {
        throw new Error(`Failed to fetch file: ${fileResponse.status} ${fileResponse.statusText}`);
      }
      
      const fileContent = await fileResponse.text();
      
      // Create a File object from the fetched content
      const fileBlob = new Blob([fileContent], { type: 'text/plain' });
      const file = new File([fileBlob], fileMetadata.filename, {
        type: 'text/plain',
        lastModified: Date.now(),
      });
      
      onFileSelect(file);
      onClose();
    } catch (error) {
      console.error('Failed to load server file:', error);
      onError(error instanceof Error ? error.message : 'Failed to load file from server');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
              <Folder className="w-4 h-4 text-white" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">Select Server File</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden" style={{ minHeight: '400px' }}>
          <FileBrowser onFileSelect={handleFileSelect} />
        </div>
      </div>
    </div>
  );
};
