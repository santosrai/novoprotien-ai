import React, { useState, useEffect, useMemo } from 'react';
import { Loader2, AlertCircle, UploadCloud, FileText, X } from 'lucide-react';
import { api, getAuthHeaders } from '../utils/api';
import { AttachmentMenu } from './AttachmentMenu';
import { useChatHistoryStore } from '../stores/chatHistoryStore';

interface ProteinMPNNParameters {
  numDesigns: number;
  temperature: number;
  chainIds: string[];
  fixedPositions: string[];
  randomSeed?: number;
  options?: Record<string, unknown>;
}

interface ProteinMPNNSources {
  rfdiffusion: Array<{
    jobId: string;
    filename: string;
    path: string;
    size: number;
    modified: number;
  }>;
  uploads: Array<{
    file_id: string;
    filename: string;
    stored_path: string;
    size: number;
    atoms: number;
    chains: string[];
  }>;
}

interface ProteinMPNNDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (payload: {
    pdbSource: 'rfdiffusion' | 'upload' | 'inline';
    sourceJobId?: string;
    uploadId?: string;
    parameters: ProteinMPNNParameters;
    message?: string;
  }) => void;
  initialData?: any;
}

interface UploadedFileState {
  file_id: string;
  filename: string;
  stored_path: string;
}

export const ProteinMPNNDialog: React.FC<ProteinMPNNDialogProps> = ({
  isOpen,
  onClose,
  onConfirm,
  initialData
}) => {
  const { activeSessionId } = useChatHistoryStore();
  const [sources, setSources] = useState<ProteinMPNNSources>({ rfdiffusion: [], uploads: [] });
  const [loadingSources, setLoadingSources] = useState(false);
  const [sourcesError, setSourcesError] = useState<string | null>(null);

  const initialSource = (initialData?.pdbSource as 'rfdiffusion' | 'upload' | 'inline') || 'rfdiffusion';
  const [sourceType, setSourceType] = useState<'rfdiffusion' | 'upload' | 'inline'>(initialSource);
  const [selectedRFJob, setSelectedRFJob] = useState<string | null>(initialData?.source?.jobId || null);
  const [selectedUpload, setSelectedUpload] = useState<UploadedFileState | null>(
    initialData?.source?.uploadId
      ? {
          file_id: initialData.source.uploadId,
          filename: initialData.source.filename || 'uploaded.pdb',
          stored_path: initialData.source.pdbPath || ''
        }
      : null
  );
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [numDesigns, setNumDesigns] = useState<number>(initialData?.parameters?.numDesigns || 5);
  const [temperature, setTemperature] = useState<number>(
    initialData?.parameters?.temperature != null ? initialData.parameters.temperature : 0.1
  );
  const [chainIdsInput, setChainIdsInput] = useState<string>((initialData?.parameters?.chainIds || []).join(', '));
  const [fixedResiduesInput, setFixedResiduesInput] = useState<string>((initialData?.parameters?.fixedPositions || []).join(', '));
  const [randomSeedInput, setRandomSeedInput] = useState<string>(
    initialData?.parameters?.randomSeed != null ? String(initialData.parameters.randomSeed) : ''
  );
  const [optionsJson, setOptionsJson] = useState<string>(
    initialData?.parameters?.options ? JSON.stringify(initialData.parameters.options, null, 2) : ''
  );
  const [message, setMessage] = useState<string>(initialData?.message || 'Ready to design sequences with ProteinMPNN.');

  const fetchSources = async () => {
    setLoadingSources(true);
    setSourcesError(null);
    try {
      const response = await api.get('/proteinmpnn/sources');
      setSources(response.data?.sources || { rfdiffusion: [], uploads: [] });
    } catch (error: any) {
      console.error('Failed to load ProteinMPNN sources', error);
      setSourcesError(error?.message || 'Failed to load available structures');
    } finally {
      setLoadingSources(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchSources();
    }
  }, [isOpen]);

  useEffect(() => {
    if (initialData?.pdbSource) {
      setSourceType(initialData.pdbSource);
    }
    if (initialData?.source?.jobId) {
      setSelectedRFJob(initialData.source.jobId);
    }
    if (initialData?.source?.uploadId) {
      setSelectedUpload({
        file_id: initialData.source.uploadId,
        filename: initialData.source.filename || 'uploaded.pdb',
        stored_path: initialData.source.pdbPath || ''
      });
    }
  }, [initialData]);

  const handleFileUploaded = (result: any) => {
    if (result.status === 'cleared') {
      setSelectedUpload(null);
      return;
    }
    if (result.file_info?.file_id) {
      setSelectedUpload({
        file_id: result.file_info.file_id,
        filename: result.file_info.filename,
        stored_path: result.file_info.file_path || result.file_info.stored_path || ''
      });
      setUploadError(null);
    }
  };

  const handleFileSelected = async (file: File) => {
    setUploadError(null);
    setUploading(true);
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
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Upload failed');
      }
      const result = await response.json();
      handleFileUploaded(result);
      await fetchSources();
    } catch (err: any) {
      setUploadError(err?.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const existingUploadOptions = useMemo(() => sources.uploads || [], [sources.uploads]);

  const formatBytes = (bytes: number) => {
    if (!bytes) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  const handleConfirm = () => {
    setFormError(null);
    try {
      let uploadId: string | undefined;
      let sourceJobId: string | undefined;

      if (sourceType === 'rfdiffusion') {
        if (!selectedRFJob) {
          setFormError('Select an RFdiffusion result to use as the backbone.');
          return;
        }
        sourceJobId = selectedRFJob;
      } else if (sourceType === 'upload') {
        if (!selectedUpload) {
          setFormError('Upload or select a PDB file to continue.');
          return;
        }
        uploadId = selectedUpload.file_id;
      } else {
        if (!initialData?.pdbContent) {
          setFormError('Inline PDB content missing. Choose another source or upload a file.');
          return;
        }
      }

      const chainIds = chainIdsInput
        .split(',')
        .map(v => v.trim())
        .filter(Boolean);
      const fixedPositions = fixedResiduesInput
        .split(',')
        .map(v => v.trim())
        .filter(Boolean);

      let options: Record<string, unknown> | undefined;
      if (optionsJson.trim()) {
        try {
          options = JSON.parse(optionsJson);
        } catch (err) {
          setFormError('Advanced options JSON is invalid.');
          return;
        }
      }

      const randomSeed = randomSeedInput.trim() ? Number(randomSeedInput.trim()) : undefined;
      if (randomSeedInput.trim() && Number.isNaN(randomSeed)) {
        setFormError('Random seed must be a number.');
        return;
      }

      onConfirm({
        pdbSource: sourceType,
        sourceJobId,
        uploadId,
        parameters: {
          numDesigns: Math.max(1, Math.min(20, Number(numDesigns) || 1)),
          temperature: Math.max(0, Number(temperature) || 0.1),
          chainIds,
          fixedPositions,
          randomSeed,
          options,
        },
        message
      });
    } catch (err: any) {
      setFormError(err?.message || 'Unable to submit design job.');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900">ProteinMPNN Sequence Design</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl"
            >
              ×
            </button>
          </div>

          {initialData?.design_info && (
            <div className="mb-6 p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <p className="text-sm text-purple-800 font-medium">{initialData.design_info.summary || 'Inverse folding request detected.'}</p>
              {initialData.design_info.notes && (
                <ul className="mt-2 text-xs text-purple-700 list-disc pl-5 space-y-1">
                  {initialData.design_info.notes.map((note: string, idx: number) => (
                    <li key={idx}>{note}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="space-y-6">
            {/* Source Selection */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-3">Choose Backbone Source</h3>
              <div className="flex space-x-2 mb-4">
                {(['rfdiffusion', 'upload'] as const).map(option => (
                  <button
                    key={option}
                    onClick={() => setSourceType(option)}
                    className={`px-3 py-1.5 text-sm rounded-lg border ${
                      sourceType === option
                        ? 'border-purple-600 bg-purple-50 text-purple-700'
                        : 'border-gray-300 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {option === 'rfdiffusion' ? 'RFdiffusion Result' : 'Upload PDB File'}
                  </button>
                ))}
              </div>

              {sourceType === 'rfdiffusion' && (
                <div className="space-y-3">
                  {loadingSources ? (
                    <div className="flex items-center text-sm text-gray-600"><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Loading RFdiffusion jobs...</div>
                  ) : sources.rfdiffusion.length === 0 ? (
                    <div className="text-sm text-gray-600 bg-gray-50 border border-dashed border-gray-300 rounded p-3 flex items-start space-x-2">
                      <AlertCircle className="w-4 h-4 mt-0.5 text-gray-500" />
                      <span>No RFdiffusion results found. Run an RFdiffusion design or upload a PDB file.</span>
                    </div>
                  ) : (
                    <select
                      value={selectedRFJob || ''}
                      onChange={(e) => setSelectedRFJob(e.target.value || null)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    >
                      <option value="">Select an RFdiffusion design...</option>
                      {sources.rfdiffusion.map(item => (
                        <option key={item.jobId} value={item.jobId}>
                          {item.jobId} • {item.filename} • {formatBytes(item.size)}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              )}

              {sourceType === 'upload' && (
                <div className="space-y-4">
                  <div className="flex items-center space-x-3">
                    <AttachmentMenu
                      onFileSelected={handleFileSelected}
                      onFileUploaded={handleFileUploaded}
                      onError={setUploadError}
                      currentFile={selectedUpload ? {
                        filename: selectedUpload.filename,
                        file_id: selectedUpload.file_id,
                        file_path: selectedUpload.stored_path
                      } : null}
                      sessionId={activeSessionId}
                    />
                    <div className="text-xs text-gray-600 flex-1">
                      <p>Upload a PDB file (max 10 MB). Designed sequences will respect this backbone.</p>
                      {uploading && (
                        <span className="inline-flex items-center mt-2 text-amber-600">
                          <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                          Uploading...
                        </span>
                      )}
                    </div>
                  </div>

                  {selectedUpload && (
                    <div className="flex items-center justify-between gap-2 px-3 py-2 bg-purple-50 border border-purple-200 rounded-lg">
                      <span className="text-sm text-purple-800 truncate" title={selectedUpload.filename}>
                        <FileText className="w-4 h-4 inline-block mr-2 text-purple-600" />
                        {selectedUpload.filename}
                      </span>
                      <button
                        type="button"
                        onClick={() => setSelectedUpload(null)}
                        className="p-1 text-purple-600 hover:text-purple-800 hover:bg-purple-100 rounded"
                        aria-label="Clear selection"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}

                  {uploadError && (
                    <div className="text-xs text-red-600 flex items-center space-x-2">
                      <AlertCircle className="w-4 h-4" />
                      <span>{uploadError}</span>
                    </div>
                  )}

                  {existingUploadOptions.length > 0 && (
                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-gray-700">Previously uploaded files</label>
                      <select
                        value={selectedUpload?.file_id || ''}
                        onChange={(e) => {
                          const file = existingUploadOptions.find(u => u.file_id === e.target.value);
                          setSelectedUpload(file ? {
                            file_id: file.file_id,
                            filename: file.filename,
                            stored_path: file.stored_path
                          } : null);
                        }}
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                      >
                        <option value="">Select uploaded file...</option>
                        {existingUploadOptions.map(file => (
                          <option key={file.file_id} value={file.file_id}>
                            {file.filename} • {formatBytes(file.size)} • Chains: {file.chains.join(', ') || 'n/a'}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Parameter Configuration */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-3">Design Parameters</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Number of designs</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={numDesigns}
                    onChange={(e) => setNumDesigns(Number(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                  <p className="text-xs text-gray-500 mt-1">Generate up to 20 candidate sequences.</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Temperature</label>
                  <input
                    type="number"
                    step={0.05}
                    min={0}
                    max={1}
                    value={temperature}
                    onChange={(e) => setTemperature(Number(e.target.value))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  />
                  <p className="text-xs text-gray-500 mt-1">Lower values bias towards conservative designs.</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Chain IDs (optional)</label>
                  <input
                    type="text"
                    value={chainIdsInput}
                    onChange={(e) => setChainIdsInput(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    placeholder="e.g. A,B"
                  />
                  <p className="text-xs text-gray-500 mt-1">Leave empty to design all chains.</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Fixed residues</label>
                  <input
                    type="text"
                    value={fixedResiduesInput}
                    onChange={(e) => setFixedResiduesInput(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    placeholder="e.g. A45,A46"
                  />
                  <p className="text-xs text-gray-500 mt-1">Residues that must remain unchanged.</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Random seed (optional)</label>
                  <input
                    type="number"
                    value={randomSeedInput}
                    onChange={(e) => setRandomSeedInput(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    placeholder="Deterministic runs when provided"
                  />
                </div>
              </div>
            </div>

            {/* Advanced options */}
            <div>
              <details className="bg-gray-50 rounded-lg border border-dashed border-gray-300">
                <summary className="px-4 py-2 cursor-pointer flex items-center space-x-2 text-sm text-gray-700">
                  <UploadCloud className="w-4 h-4" />
                  <span>Advanced ProteinMPNN options (JSON)</span>
                </summary>
                <div className="p-4 border-t border-gray-200">
                  <textarea
                    value={optionsJson}
                    onChange={(e) => setOptionsJson(e.target.value)}
                    className="w-full h-32 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
                    placeholder={`{\n  "bias_by_residue": { "A": 0.5 }\n}`}
                  />
                  <p className="text-xs text-gray-500 mt-2">
                    Optional advanced controls passed directly to the ProteinMPNN API. Provide valid JSON.
                  </p>
                </div>
              </details>
            </div>

            {/* Summary */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirmation message</label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                rows={2}
              />
            </div>

            {formError && (
              <div className="flex items-start space-x-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
                <AlertCircle className="w-4 h-4 mt-0.5" />
                <span>{formError}</span>
              </div>
            )}

            {sourcesError && (
              <div className="flex items-start space-x-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
                <AlertCircle className="w-4 h-4 mt-0.5" />
                <span>{sourcesError}</span>
              </div>
            )}
          </div>
        </div>

        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className="inline-flex items-center px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700"
          >
            <FileText className="w-4 h-4 mr-2" />
            Confirm Design
          </button>
        </div>
      </div>
    </div>
  );
};

