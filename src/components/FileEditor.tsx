import React, { useState, useEffect } from 'react';
import { X, Download, FileText, Play } from 'lucide-react';
import { api, getAuthHeaders } from '../utils/api';
import { useAppStore } from '../stores/appStore';
import { useChatHistoryStore } from '../stores/chatHistoryStore';
import { CodeExecutor } from '../utils/codeExecutor';

interface FileEditorProps {
  fileId: string;
  filename: string;
  fileType: string;
  onClose: () => void;
}

export const FileEditor: React.FC<FileEditorProps> = ({ fileId, filename, fileType, onClose }) => {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { plugin, setActivePane, setViewerVisible, setIsExecuting, setCurrentCode, setCurrentStructureOrigin } = useAppStore();
  const { activeSessionId, saveVisualizationCode } = useChatHistoryStore();

  useEffect(() => {
    const loadFile = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await api.get(`/files/${fileId}`);
        
        if (response.data.status === 'success') {
          setContent(response.data.content || '');
        } else {
          setError('Failed to load file content');
        }
      } catch (err: any) {
        console.error('[FileEditor] Failed to load file:', err);
        setError(err.response?.data?.detail || err.message || 'Failed to load file');
      } finally {
        setLoading(false);
      }
    };

    loadFile();
  }, [fileId]);

  const handleDownload = async () => {
    try {
      const response = await api.get(`/files/${fileId}`, {
        responseType: 'blob',
      });
      
      const blob = new Blob([response.data], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      console.error('[FileEditor] Failed to download file:', err);
      alert('Failed to download file');
    }
  };

  const handleView3D = async () => {
    if (!plugin) {
      alert('3D viewer is not initialized. Please wait a moment and try again.');
      return;
    }

    try {
      setIsExecuting(true);
      const executor = new CodeExecutor(plugin);

      // Construct file URL based on file type
      let fileUrl: string;
      if (fileType === 'upload') {
        fileUrl = `/api/upload/pdb/${fileId}`;
      } else {
        fileUrl = `/api/files/${fileId}/download`;
      }

      // Fetch file content with authentication headers
      const headers = getAuthHeaders();
      const fileResponse = await fetch(fileUrl, { headers });
      if (!fileResponse.ok) {
        throw new Error(`Failed to fetch file: ${fileResponse.status} ${fileResponse.statusText}`);
      }
      const fileContent = await fileResponse.text();

      // Create blob URL
      const pdbBlob = new Blob([fileContent], { type: 'text/plain' });
      const blobUrl = URL.createObjectURL(pdbBlob);

      // Load structure in viewer using blob URL
      const code = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${blobUrl}');
  await builder.addCartoonRepresentation({ color: 'secondary-structure' });
  builder.focusView();
  console.log('Successfully loaded ${filename} in 3D viewer');
} catch (e) { 
  console.error('Failed to load file in 3D viewer:', e); 
}`;

      // Save code to editor so user can see and modify it
      setCurrentCode(code);

      // Set structure origin for LLM context
      setCurrentStructureOrigin({
        type: fileType as 'upload' | 'rfdiffusion' | 'alphafold',
        filename: filename,
        metadata: {
          file_id: fileId,
          file_url: fileUrl,
        },
      });

      // Save code to active session for persistence
      if (activeSessionId) {
        saveVisualizationCode(activeSessionId, code);
        console.log('[FileEditor] Saved visualization code to session:', activeSessionId);
      }

      await executor.executeCode(code);

      // Switch to viewer pane and make it visible
      setViewerVisible(true);
      setActivePane('viewer');
    } catch (err: any) {
      console.error('[FileEditor] Failed to load file in 3D viewer:', err);
      alert(`Failed to load file in 3D viewer: ${err.message || 'Unknown error'}`);
    } finally {
      setIsExecuting(false);
    }
  };

  // Check if file is a PDB file that can be viewed in 3D
  const isPdbFile = filename.toLowerCase().endsWith('.pdb') || 
                    fileType === 'upload' || 
                    fileType === 'rfdiffusion' || 
                    fileType === 'alphafold';

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-gray-600" />
          <span className="text-sm font-medium text-gray-900">{filename}</span>
          <span className="text-xs text-gray-500">({fileType})</span>
        </div>
        <div className="flex items-center gap-2">
          {isPdbFile && (
            <button
              onClick={handleView3D}
              disabled={!plugin}
              className="flex items-center space-x-1 px-3 py-2 bg-white text-blue-600 hover:bg-gray-100 rounded-md disabled:opacity-50 disabled:cursor-not-allowed text-sm transition-colors"
              title="View in 3D canvas"
            >
              <Play className="w-4 h-4" />
              <span>View in 3D</span>
            </button>
          )}
          <button
            onClick={handleDownload}
            className="p-1.5 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded transition-colors"
            title="Download file"
          >
            <Download className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded transition-colors"
            title="Close editor"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-400 mx-auto mb-2"></div>
              <p className="text-sm text-gray-500">Loading file...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-sm text-red-600 mb-2">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="text-sm text-blue-600 hover:text-blue-800 underline"
              >
                Reload page
              </button>
            </div>
          </div>
        ) : (
          <pre className="text-xs font-mono text-gray-800 whitespace-pre-wrap break-words">
            {content}
          </pre>
        )}
      </div>
    </div>
  );
};
