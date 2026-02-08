import React, { useState, useEffect } from 'react';
import { X, Download, FileText, Play } from 'lucide-react';
import { api } from '../utils/api';
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
  const { plugin, setActivePane, setViewerVisible, setIsExecuting, setCurrentCode, setCurrentStructureOrigin, setPendingCodeToRun } = useAppStore();
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
    // Wait for plugin to be ready (with timeout and retry)
    const waitForPlugin = async (maxWait = 5000, retryInterval = 100): Promise<boolean> => {
      const startTime = Date.now();
      while (Date.now() - startTime < maxWait) {
        if (plugin) {
          try {
            if (plugin.builders && plugin.builders.data && plugin.builders.structure) {
              return true;
            }
          } catch (e) {
            // Plugin exists but might not be fully ready
          }
        }
        await new Promise(resolve => setTimeout(resolve, retryInterval));
      }
      return false;
    };

    // Fetch file with auth (Molstar's fetch won't include JWT) and create blob URL
    const apiPath = fileType === 'upload' ? `/upload/pdb/${fileId}` : `/files/${fileId}/download`;
    let loadUrl: string;
    try {
      const response = await api.get(apiPath, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'chemical/x-pdb' });
      loadUrl = URL.createObjectURL(blob);
      // Revoke after Molstar has fetched (avoid memory leak)
      setTimeout(() => URL.revokeObjectURL(loadUrl), 15000);
    } catch (err: any) {
      console.error('[FileEditor] Failed to fetch file for 3D:', err);
      alert(`Failed to load file: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      return;
    }

    const fileUrlForContext = fileType === 'upload' ? `/api/upload/pdb/${fileId}` : `/api/files/${fileId}/download`;
    const code = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${loadUrl}');
  await builder.addCartoonRepresentation({ color: 'secondary-structure' });
  builder.focusView();
  console.log('Successfully loaded ${filename} in 3D viewer');
} catch (e) { 
  console.error('Failed to load file in 3D viewer:', e); 
}`;

    // Save code to editor so user can see and modify it (use API path for saved code - blob URLs expire)
    const savedCode = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${fileUrlForContext}');
  await builder.addCartoonRepresentation({ color: 'secondary-structure' });
  builder.focusView();
  console.log('Successfully loaded ${filename} in 3D viewer');
} catch (e) { 
  console.error('Failed to load file in 3D viewer:', e); 
}`;
    setCurrentCode(savedCode);

    // Set structure origin for LLM context
    setCurrentStructureOrigin({
      type: fileType as 'upload' | 'rfdiffusion' | 'alphafold',
      filename: filename,
      metadata: {
        file_id: fileId,
        file_url: fileUrlForContext,
      },
    });

    // Save code to active session for persistence (use API path, not blob)
    if (activeSessionId) {
      saveVisualizationCode(activeSessionId, savedCode);
      console.log('[FileEditor] Saved visualization code to session:', activeSessionId);
    }

    const isPluginReady = await waitForPlugin();
    if (!isPluginReady) {
      console.warn('[FileEditor] Plugin not ready, queueing code for execution');
      setPendingCodeToRun(code);
      setViewerVisible(true);
      setActivePane('viewer');
      return;
    }

    if (!plugin) {
      console.warn('[FileEditor] Plugin not available, cannot execute code');
      return;
    }

    try {
      setIsExecuting(true);
      const executor = new CodeExecutor(plugin);
      await executor.executeCode(code);

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
