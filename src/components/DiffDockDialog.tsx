import React, { useState, useEffect } from 'react';
import { ErrorDisplay } from './ErrorDisplay';
import { DiffDockErrorHandler } from '../utils/errorHandler';
import { useFiles } from '../hooks/queries/useFiles';
import type { DiffDockParameters } from '../hooks/mutations/useDiffDock';

export interface DiffDockSubmitParams {
  protein_file_id?: string;
  protein_content?: string;
  ligand_sdf_content: string;
  parameters: DiffDockParameters;
}

interface DiffDockDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (params: DiffDockSubmitParams) => void;
  initialData?: Record<string, unknown>;
}

const DEFAULT_PARAMS: DiffDockParameters = {
  num_poses: 10,
  time_divisions: 20,
  steps: 18,
  save_trajectory: false,
  is_staged: true,
};

export const DiffDockDialog: React.FC<DiffDockDialogProps> = ({
  isOpen,
  onClose,
  onConfirm,
  initialData: _initialData,
}) => {
  const { data: files = [] } = useFiles();
  const uploads = files.filter((f) => f.type === 'upload');

  const [proteinSource, setProteinSource] = useState<'upload' | 'file'>('upload');
  const [proteinFileId, setProteinFileId] = useState<string>('');
  const [proteinContent, setProteinContent] = useState<string>('');
  const [ligandSdfContent, setLigandSdfContent] = useState<string>('');
  const [ligandFileName, setLigandFileName] = useState<string>('');
  const [parameters, setParameters] = useState<DiffDockParameters>(DEFAULT_PARAMS);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [validationError, setValidationError] = useState<ReturnType<typeof DiffDockErrorHandler.createError> | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setValidationError(null);
    if (uploads.length > 0 && !proteinFileId) {
      setProteinFileId(uploads[0].file_id);
    }
  }, [isOpen, uploads, proteinFileId]);

  const handleLigandFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setLigandSdfContent(String(reader.result ?? ''));
      setLigandFileName(file.name);
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleProteinFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setProteinContent(String(reader.result ?? ''));
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const validate = (): boolean => {
    setValidationError(null);
    if (!ligandSdfContent || !ligandSdfContent.trim()) {
      setValidationError(DiffDockErrorHandler.createError('VALIDATION', {}, 'Ligand SDF is required'));
      return false;
    }
    if (proteinSource === 'upload') {
      if (!proteinFileId) {
        setValidationError(DiffDockErrorHandler.createError('VALIDATION', {}, 'Select an uploaded protein or upload a PDB file'));
        return false;
      }
    } else {
      if (!proteinContent || !proteinContent.trim()) {
        setValidationError(DiffDockErrorHandler.createError('VALIDATION', {}, 'Upload a PDB file for the protein'));
        return false;
      }
    }
    return true;
  };

  const handleConfirm = () => {
    if (!validate()) return;
    onConfirm({
      protein_file_id: proteinSource === 'upload' ? proteinFileId : undefined,
      protein_content: proteinSource === 'file' ? proteinContent : undefined,
      ligand_sdf_content: ligandSdfContent,
      parameters,
    });
  };

  const hasProtein = proteinSource === 'upload' ? !!proteinFileId : !!proteinContent?.trim();
  const hasLigand = !!ligandSdfContent?.trim();
  const isValid = hasProtein && hasLigand;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              DiffDock Protein-Ligand Docking
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl"
            >
              ×
            </button>
          </div>

          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Predict how a small molecule (ligand) binds to a protein. Provide a protein PDB and a ligand SDF file.
          </p>

          {/* Protein input */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Protein (PDB)
            </label>
            <div className="flex flex-wrap gap-4 items-center mb-2">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="proteinSource"
                  checked={proteinSource === 'upload'}
                  onChange={() => setProteinSource('upload')}
                  className="text-blue-600"
                />
                <span className="text-sm">Use uploaded PDB</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="proteinSource"
                  checked={proteinSource === 'file'}
                  onChange={() => setProteinSource('file')}
                  className="text-blue-600"
                />
                <span className="text-sm">Upload PDB file</span>
              </label>
            </div>
            {proteinSource === 'upload' && (
              <select
                value={proteinFileId}
                onChange={(e) => setProteinFileId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-gray-100 text-sm"
              >
                <option value="">Select a file...</option>
                {uploads.map((f) => (
                  <option key={f.file_id} value={f.file_id}>
                    {f.filename}
                  </option>
                ))}
              </select>
            )}
            {proteinSource === 'file' && (
              <div className="flex items-center gap-2">
                <input
                  type="file"
                  accept=".pdb,.ent"
                  onChange={handleProteinFileChange}
                  className="text-sm text-gray-600 dark:text-gray-400 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/30 dark:file:text-blue-300"
                />
                {proteinContent && (
                  <span className="text-xs text-green-600">PDB loaded ({proteinContent.length} chars)</span>
                )}
              </div>
            )}
          </div>

          {/* Ligand input */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Ligand (SDF file, required)
            </label>
            <div className="flex items-center gap-2">
              <input
                type="file"
                accept=".sdf,.mol"
                onChange={handleLigandFileChange}
                className="text-sm text-gray-600 dark:text-gray-400 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/30 dark:file:text-blue-300"
              />
              {ligandFileName && (
                <span className="text-xs text-green-600">
                  {ligandFileName} ({ligandSdfContent.length} chars)
                </span>
              )}
            </div>
          </div>

          {/* Advanced parameters */}
          <div className="mb-4">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center space-x-2 text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400"
            >
              <svg
                className={`w-4 h-4 transform ${showAdvanced ? 'rotate-90' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span>{showAdvanced ? 'Hide' : 'Show'} Advanced</span>
            </button>
          </div>
          {showAdvanced && (
            <div className="mb-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Num poses
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={parameters.num_poses ?? 10}
                  onChange={(e) =>
                    setParameters((p) => ({ ...p, num_poses: parseInt(e.target.value, 10) || 10 }))
                  }
                  className="w-24 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded dark:bg-gray-800 dark:text-gray-100 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Time divisions
                </label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={parameters.time_divisions ?? 20}
                  onChange={(e) =>
                    setParameters((p) => ({ ...p, time_divisions: parseInt(e.target.value, 10) || 20 }))
                  }
                  className="w-24 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded dark:bg-gray-800 dark:text-gray-100 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Steps
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={parameters.steps ?? 18}
                  onChange={(e) =>
                    setParameters((p) => ({ ...p, steps: parseInt(e.target.value, 10) || 18 }))
                  }
                  className="w-24 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded dark:bg-gray-800 dark:text-gray-100 text-sm"
                />
              </div>
              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={parameters.save_trajectory ?? false}
                  onChange={(e) =>
                    setParameters((p) => ({ ...p, save_trajectory: e.target.checked }))
                  }
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">Save trajectory</span>
              </label>
              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={parameters.is_staged ?? true}
                  onChange={(e) =>
                    setParameters((p) => ({ ...p, is_staged: e.target.checked }))
                  }
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">Staged inference</span>
              </label>
            </div>
          )}

          {validationError && (
            <div className="mb-4">
              <ErrorDisplay error={validationError} onRetry={() => setValidationError(null)} />
            </div>
          )}

          <div className="flex justify-end space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 dark:text-gray-300 bg-gray-200 dark:bg-gray-700 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={!isValid}
              className={`px-6 py-2 rounded-lg font-medium focus:ring-2 focus:ring-offset-2 ${
                isValid
                  ? 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed dark:bg-gray-600'
              }`}
            >
              Run DiffDock
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
