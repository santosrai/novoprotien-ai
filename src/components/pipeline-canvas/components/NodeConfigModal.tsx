import React, { useState, useEffect, useRef } from 'react';
import { X, Check, Upload, File, Eye, Sparkles, Dna, Layers, FileInput } from 'lucide-react';
import { PipelineNodeBlueprint } from '../dist';
import { useChatHistoryStore } from '../../../stores/chatHistoryStore';
import { useAppStore } from '../../../stores/appStore';
import { CodeExecutor } from '../../../utils/codeExecutor';
import { getAuthHeaders } from '../../../utils/api';
import { ServerFilesDialog } from '../../ServerFilesDialog';

interface NodeConfigModalProps {
  isOpen: boolean;
  node: PipelineNodeBlueprint;
  onClose: () => void;
  onSave: (config: Record<string, any>) => void;
}

const nodeIcons: Record<string, React.ReactNode> = {
  input_node: <FileInput className="w-5 h-5" />,
  rfdiffusion_node: <Sparkles className="w-5 h-5" />,
  proteinmpnn_node: <Dna className="w-5 h-5" />,
  alphafold_node: <Layers className="w-5 h-5" />,
};

const nodeColors: Record<string, string> = {
  input_node: 'bg-blue-500',
  rfdiffusion_node: 'bg-purple-500',
  proteinmpnn_node: 'bg-green-500',
  alphafold_node: 'bg-orange-500',
};

export const NodeConfigModal: React.FC<NodeConfigModalProps> = ({
  isOpen,
  node,
  onClose,
  onSave,
}) => {
  const { activeSessionId } = useChatHistoryStore();
  const { plugin, setCurrentCode, setViewerVisible, setActivePane, setCurrentStructureOrigin } = useAppStore();
  const [config, setConfig] = useState<Record<string, any>>(node.config || {});
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pdbId, setPdbId] = useState<string>('');
  const [isLoadingViewer, setIsLoadingViewer] = useState(false);
  const [showServerFiles, setShowServerFiles] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Initialize config from node
  useEffect(() => {
    if (isOpen) {
      const defaults = getDefaultConfig(node.type);
      setConfig({ ...defaults, ...(node.config || {}) });
      if (node.config?.pdb_id) {
        setPdbId(node.config.pdb_id);
      } else {
        setPdbId('');
      }
      setUploadError(null);
      setPendingFile(null);
    }
  }, [isOpen, node.config, node.type]);

  const getDefaultConfig = (nodeType: string): Record<string, any> => {
    switch (nodeType) {
      case 'input_node':
        return { filename: '' };
      case 'rfdiffusion_node':
        return {
          contigs: 'A50-150',
          num_designs: 1,
          diffusion_steps: 15,
          design_mode: 'unconditional',
          hotspot_res: '',
          pdb_id: '',
        };
      case 'proteinmpnn_node':
        return {
          num_sequences: 8,
          temperature: 0.1,
        };
      case 'alphafold_node':
        return {
          recycle_count: 3,
          num_relax: 0,
        };
      default:
        return {};
    }
  };

  const getConfigFields = (nodeType: string) => {
    switch (nodeType) {
      case 'input_node':
        return [];
      case 'rfdiffusion_node':
        return [
          {
            key: 'contigs',
            label: 'Contigs',
            type: 'string',
            placeholder: 'A50-150',
            helpText: 'Contig specification (e.g., "A50-150" or "A20-60/0 50-100")',
          },
          {
            key: 'num_designs',
            label: 'Number of Designs',
            type: 'number',
            min: 1,
            max: 10,
            default: 1,
          },
          {
            key: 'diffusion_steps',
            label: 'Diffusion Steps',
            type: 'number',
            min: 1,
            max: 100,
            default: 15,
            helpText: 'Number of diffusion steps (1-100, higher = better quality but slower)',
          },
          {
            key: 'design_mode',
            label: 'Design Mode',
            type: 'select',
            options: [
              { value: 'unconditional', label: 'Unconditional Design' },
              { value: 'motif_scaffolding', label: 'Motif Scaffolding' },
              { value: 'partial_diffusion', label: 'Partial Diffusion' },
            ],
            default: 'unconditional',
          },
          {
            key: 'hotspot_res',
            label: 'Hotspot Residues',
            type: 'string',
            placeholder: 'A50, A51, A52',
            helpText: 'Comma-separated list of residues to preserve',
          },
          {
            key: 'pdb_id',
            label: 'PDB ID (Template)',
            type: 'string',
            placeholder: 'e.g., 1R42',
            helpText: 'Optional PDB ID to use as template',
          },
        ];
      case 'proteinmpnn_node':
        return [
          {
            key: 'num_sequences',
            label: 'Number of Sequences',
            type: 'number',
            min: 1,
            max: 100,
            default: 8,
          },
          {
            key: 'temperature',
            label: 'Temperature',
            type: 'number',
            min: 0.1,
            max: 1.0,
            step: 0.1,
            default: 0.1,
          },
        ];
      case 'alphafold_node':
        return [
          {
            key: 'recycle_count',
            label: 'Recycle Count',
            type: 'number',
            min: 1,
            max: 20,
            default: 3,
          },
          {
            key: 'num_relax',
            label: 'Number of Relax Steps',
            type: 'number',
            min: 0,
            max: 10,
            default: 0,
          },
        ];
      default:
        return [];
    }
  };

  const handleFieldChange = (key: string, value: any) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleFileSelect = (file: File) => {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdb')) {
      setUploadError('Please select a PDB file (.pdb extension required)');
      return;
    }

    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      setUploadError('File too large. Maximum size is 10MB.');
      return;
    }

    setPendingFile(file);
    setUploadError(null);
    if (node.type === 'input_node') {
      handleFileUpload(file);
    }
  };

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (activeSessionId) {
        formData.append('session_id', activeSessionId);
      }

      const headers = getAuthHeaders();

      const response = await fetch('/api/upload/pdb', {
        method: 'POST',
        headers,
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const result = await response.json();
      
      let fileUrl = result.file_info.file_url || `/api/upload/pdb/${result.file_info.file_id}`;
      if (fileUrl.startsWith('/')) {
        fileUrl = `${window.location.origin}${fileUrl}`;
      }
      
      const updatedConfig = {
        ...config,
        filename: result.file_info.filename,
        file_id: result.file_info.file_id,
        file_url: fileUrl,
        ...(result.file_info.chain_residue_counts && { chain_residue_counts: result.file_info.chain_residue_counts }),
        ...(result.file_info.total_residues && { total_residues: result.file_info.total_residues }),
        ...(result.file_info.suggested_contigs && { suggested_contigs: result.file_info.suggested_contigs }),
        ...(result.file_info.chains && { chains: result.file_info.chains }),
        ...(result.file_info.atoms && { atoms: result.file_info.atoms }),
      };
      
      setConfig(updatedConfig);
      setPendingFile(null);
    } catch (error: any) {
      console.error('[NodeConfigModal] File upload failed:', error);
      setUploadError(error.message || 'Upload failed');
      setPendingFile(null);
    } finally {
      setIsUploading(false);
    }
  };

  const loadFileInViewer = async (urlOrPdbId: string, filename?: string) => {
    if (!plugin) return;
    
    try {
      setIsLoadingViewer(true);
      const executor = new CodeExecutor(plugin);
      
      const isUrl = urlOrPdbId.startsWith('http://') || urlOrPdbId.startsWith('https://') || urlOrPdbId.startsWith('/api/');
      
      let loadUrl = urlOrPdbId;
      if (!isUrl) {
        loadUrl = `https://files.rcsb.org/view/${urlOrPdbId.toUpperCase()}.pdb`;
      }
      
      const code = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${loadUrl}');
  await builder.addCartoonRepresentation({ color: 'secondary-structure' });
  builder.focusView();
  console.log('Structure loaded successfully');
} catch (e) { 
  console.error('Failed to load structure:', e); 
}`;
      
      setCurrentCode(code);
      await executor.executeCode(code);
      setViewerVisible(true);
      setActivePane('viewer');
      
      setCurrentStructureOrigin({
        type: isUrl ? 'upload' : 'pdb',
        filename: filename || urlOrPdbId,
        pdbId: isUrl ? undefined : urlOrPdbId,
        metadata: { source: isUrl ? 'upload' : 'pdb_id' }
      });
    } catch (error) {
      console.error('[NodeConfigModal] Failed to load structure in viewer:', error);
      setUploadError('Failed to load structure in viewer');
    } finally {
      setIsLoadingViewer(false);
    }
  };

  const handlePdbIdChange = (value: string) => {
    setPdbId(value);
    const updatedConfig = {
      ...config,
      pdb_id: value,
      ...(value ? { file_id: undefined, file_url: undefined, filename: undefined } : {}),
    };
    setConfig(updatedConfig);
  };

  const handleLoadPdbId = async () => {
    if (!pdbId.trim()) return;
    
    const pdbIdRegex = /^[0-9A-Za-z]{4}$/;
    if (!pdbIdRegex.test(pdbId.trim())) {
      setUploadError('Invalid PDB ID format. Must be 4 alphanumeric characters (e.g., 1ABC)');
      return;
    }
    
    setUploadError(null);
    const upperPdbId = pdbId.trim().toUpperCase();
    const updatedConfig = {
      ...config,
      pdb_id: upperPdbId,
      filename: `${upperPdbId}.pdb`,
    };
    setConfig(updatedConfig);
    await loadFileInViewer(upperPdbId);
  };

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
    event.target.value = '';
  };

  const handleSave = () => {
    // For input nodes, ensure either file is uploaded or PDB ID is provided
    if (node.type === 'input_node' && !config.file_id && !config.pdb_id && !pendingFile) {
      setUploadError('Please upload a PDB file, select from server files, or enter a PDB ID');
      return;
    }
    onSave(config);
    onClose();
  };

  if (!isOpen) return null;

  const fields = getConfigFields(node.type);
  const nodeColor = nodeColors[node.type] || 'bg-gray-500';
  const nodeIcon = nodeIcons[node.type] || <FileInput className="w-5 h-5" />;

  return (
    <>
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
        <div
          className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 sm:p-6 border-b border-gray-200 flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded ${nodeColor} flex items-center justify-center text-white`}>
                {nodeIcon}
              </div>
              <div>
                <h2 className="text-lg sm:text-xl font-semibold text-gray-900">Configure {node.label}</h2>
                <p className="text-xs text-gray-500 mt-0.5">{node.type}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6">
            <div className="space-y-4">
              {/* Input Node File Upload Section */}
              {node.type === 'input_node' && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    PDB File <span className="text-red-500">*</span>
                  </label>
                  <p className="text-xs text-gray-600 mb-4">
                    Upload a PDB file, select from server files, or enter a PDB ID to use as input for this pipeline
                  </p>
                  
                  {config.file_id ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-md">
                        <div className="flex items-center space-x-2 flex-1 min-w-0">
                          <File className="w-4 h-4 text-green-600 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-green-800 truncate">{config.filename}</p>
                            {config.chains && (
                              <p className="text-xs text-green-600">
                                Chains: {config.chains.join(', ')} • {config.atoms || 0} atoms
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center space-x-2 ml-2 flex-shrink-0">
                          <button
                            type="button"
                            onClick={() => loadFileInViewer(config.file_url, config.filename)}
                            disabled={isLoadingViewer}
                            className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 transition-colors disabled:opacity-50 flex items-center space-x-1"
                            title="View in 3D canvas"
                          >
                            <Eye className="w-3 h-3" />
                            <span>View</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setConfig(prev => {
                                const newConfig = { ...prev };
                                delete newConfig.file_id;
                                delete newConfig.filename;
                                delete newConfig.file_url;
                                return newConfig;
                              });
                            }}
                            className="text-xs text-green-700 hover:text-green-900 underline"
                          >
                            Change
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : config.pdb_id ? (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-md">
                        <div className="flex items-center space-x-2 flex-1">
                          <File className="w-4 h-4 text-blue-600 flex-shrink-0" />
                          <div>
                            <p className="text-sm font-medium text-blue-800">PDB ID: {config.pdb_id}</p>
                            <p className="text-xs text-blue-600">Retrieved from RCSB PDB database</p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2 ml-2">
                          <button
                            type="button"
                            onClick={() => loadFileInViewer(config.pdb_id)}
                            disabled={isLoadingViewer}
                            className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors disabled:opacity-50 flex items-center space-x-1"
                            title="View in 3D canvas"
                          >
                            <Eye className="w-3 h-3" />
                            <span>View</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setPdbId('');
                              setConfig(prev => {
                                const newConfig = { ...prev };
                                delete newConfig.pdb_id;
                                return newConfig;
                              });
                            }}
                            className="text-xs text-blue-700 hover:text-blue-900 underline"
                          >
                            Change
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-2">Option 1: Upload File</label>
                        <button
                          type="button"
                          onClick={() => fileInputRef.current?.click()}
                          disabled={isUploading}
                          className="w-full flex items-center justify-center space-x-2 px-4 py-3 border-2 border-dashed border-gray-300 rounded-md hover:border-blue-400 hover:bg-blue-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isUploading ? (
                            <>
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                              <span className="text-sm text-gray-600">Uploading...</span>
                            </>
                          ) : (
                            <>
                              <Upload className="w-4 h-4 text-gray-600" />
                              <span className="text-sm text-gray-700">Click to upload PDB file</span>
                            </>
                          )}
                        </button>
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept=".pdb"
                          onChange={handleFileInputChange}
                          className="hidden"
                        />
                        {pendingFile && (
                          <p className="mt-2 text-xs text-gray-600">
                            Selected: {pendingFile.name}
                          </p>
                        )}
                      </div>
                      
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-2">Option 2: Select from Server</label>
                        <button
                          type="button"
                          onClick={() => setShowServerFiles(true)}
                          className="w-full flex items-center justify-center space-x-2 px-4 py-3 border border-gray-300 rounded-md hover:border-blue-400 hover:bg-blue-50 transition-colors"
                        >
                          <File className="w-4 h-4 text-gray-600" />
                          <span className="text-sm text-gray-700">Browse server files</span>
                        </button>
                      </div>
                      
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-2">Option 3: PDB ID</label>
                        <div className="flex items-center space-x-2">
                          <input
                            type="text"
                            value={pdbId}
                            onChange={(e) => handlePdbIdChange(e.target.value)}
                            placeholder="e.g., 1ABC"
                            maxLength={4}
                            className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase"
                          />
                          <button
                            type="button"
                            onClick={handleLoadPdbId}
                            disabled={!pdbId.trim() || isLoadingViewer}
                            className="px-3 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-1"
                          >
                            {isLoadingViewer ? (
                              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                            ) : (
                              <>
                                <Eye className="w-4 h-4" />
                                <span>Load</span>
                              </>
                            )}
                          </button>
                        </div>
                        <p className="mt-1 text-xs text-gray-500">
                          Enter a 4-character PDB ID to retrieve from RCSB database
                        </p>
                      </div>
                    </div>
                  )}
                  
                  {uploadError && (
                    <p className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">{uploadError}</p>
                  )}
                </div>
              )}

              {/* Regular Configuration Fields */}
              {fields.map((field) => {
                const isStringField = field.type === 'string';
                const isNumberField = field.type === 'number';
                const isSelectField = field.type === 'select';
                
                return (
                  <div key={field.key} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {field.label}
                      {('required' in field && (field as any).required) ? <span className="text-red-500 ml-1">*</span> : null}
                    </label>
                    {'helpText' in field && field.helpText && (
                      <p className="text-xs text-gray-500 mb-2">{field.helpText}</p>
                    )}
                    {isStringField && 'placeholder' in field && (
                      <input
                        type="text"
                        value={config[field.key] || ''}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    )}
                    {isNumberField && (
                      <input
                        type="number"
                        value={config[field.key] ?? ('default' in field ? field.default : undefined) ?? ''}
                        onChange={(e) => handleFieldChange(field.key, parseFloat(e.target.value) || 0)}
                        min={'min' in field ? field.min : undefined}
                        max={'max' in field ? field.max : undefined}
                        step={'step' in field ? field.step : 1}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    )}
                    {isSelectField && 'options' in field && (
                      <select
                        value={config[field.key] || ('default' in field ? field.default : '') || ''}
                        onChange={(e) => handleFieldChange(field.key, e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {field.options?.map((opt: { value: string; label: string }) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end space-x-3 p-4 sm:p-6 border-t border-gray-200 flex-shrink-0">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={node.type === 'input_node' && !config.file_id && !config.pdb_id && !pendingFile}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              <Check className="w-4 h-4" />
              <span>Save Configuration</span>
            </button>
          </div>
        </div>
      </div>

      {/* Server Files Dialog */}
      {node.type === 'input_node' && (
        <ServerFilesDialog
          isOpen={showServerFiles}
          onClose={() => setShowServerFiles(false)}
          onFileSelect={handleFileSelect}
          onError={(error) => setUploadError(error)}
        />
      )}
    </>
  );
};
