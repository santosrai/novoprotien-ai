import React, { useState } from 'react';
import { ErrorDisplay } from './ErrorDisplay';
import { OpenFold2ErrorHandler } from '../utils/errorHandler';

export interface OpenFold2Parameters {
  alignmentsRaw?: string;
  templatesRaw?: string;
  relax_prediction: boolean;
}

interface OpenFold2DialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (sequence: string, parameters: OpenFold2Parameters) => void;
}

const VALID_AA = /^[ACDEFGHIKLMNPQRSTVWY\s]*$/i;
const MAX_SEQUENCE_LENGTH = 1000;

export const OpenFold2Dialog: React.FC<OpenFold2DialogProps> = ({
  isOpen,
  onClose,
  onConfirm,
}) => {
  const [sequence, setSequence] = useState('');
  const [parameters, setParameters] = useState<OpenFold2Parameters>({
    alignmentsRaw: undefined,
    templatesRaw: undefined,
    relax_prediction: false,
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [validationError, setValidationError] = useState<ReturnType<typeof OpenFold2ErrorHandler.handleSequenceValidation> | null>(null);

  const cleanSeq = sequence.replace(/\s/g, '').toUpperCase();
  const seqLength = cleanSeq.length;
  const isValid =
    cleanSeq.length >= 20 &&
    cleanSeq.length <= MAX_SEQUENCE_LENGTH &&
    VALID_AA.test(cleanSeq);

  const validate = () => {
    const err = OpenFold2ErrorHandler.handleSequenceValidation(sequence);
    setValidationError(err);
    return !err;
  };

  const handleMsaFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setParameters((p) => ({ ...p, alignmentsRaw: reader.result as string }));
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleTemplateFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setParameters((p) => ({ ...p, templatesRaw: reader.result as string }));
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  const handleConfirm = () => {
    if (!validate()) return;
    onConfirm(cleanSeq, parameters);
  };

  const clearMsa = () => setParameters((p) => ({ ...p, alignmentsRaw: undefined }));
  const clearTemplate = () => setParameters((p) => ({ ...p, templatesRaw: undefined }));

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              OpenFold2 Structure Prediction
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-2xl"
            >
              ×
            </button>
          </div>

          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Predict 3D structure from sequence. Optional: upload MSA (a3m) and templates (hhr) for improved accuracy.
          </p>

          {/* Sequence Input */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Protein Sequence (required, max 1000 residues)
            </label>
            <textarea
              value={sequence}
              onChange={(e) => setSequence(e.target.value)}
              className={`w-full h-32 px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-100 ${
                validationError ? 'border-red-300 bg-red-50 dark:bg-red-900/20' : 'border-gray-300'
              }`}
              placeholder="Enter protein sequence (ACDEFGHIKLMNPQRSTVWY)..."
            />
            <div className="mt-2 flex justify-between items-center text-sm">
              <span className={isValid ? 'text-green-600' : 'text-amber-600'}>
                {seqLength} residues {seqLength > MAX_SEQUENCE_LENGTH && '(exceeds 1000 — use AlphaFold2)'}
              </span>
            </div>
            {validationError && (
              <div className="mt-2">
                <ErrorDisplay error={validationError} onRetry={() => setValidationError(null)} />
              </div>
            )}
          </div>

          {/* Collapsible Advanced */}
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
              <span>{showAdvanced ? 'Hide' : 'Show'} Advanced (MSA & Template)</span>
            </button>
          </div>

          {showAdvanced && (
            <div className="mb-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  MSA File (a3m format, optional)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="file"
                    accept=".a3m,.txt"
                    onChange={handleMsaFileChange}
                    className="text-sm text-gray-600 dark:text-gray-400 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/30 dark:file:text-blue-300"
                  />
                  {parameters.alignmentsRaw && (
                    <button
                      type="button"
                      onClick={clearMsa}
                      className="text-sm text-red-600 hover:text-red-800"
                    >
                      Clear
                    </button>
                  )}
                </div>
                {parameters.alignmentsRaw && (
                  <p className="text-xs text-green-600 mt-1">
                    MSA loaded ({parameters.alignmentsRaw.length} chars)
                  </p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Template File (hhr format, optional)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="file"
                    accept=".hhr,.txt"
                    onChange={handleTemplateFileChange}
                    className="text-sm text-gray-600 dark:text-gray-400 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/30 dark:file:text-blue-300"
                  />
                  {parameters.templatesRaw && (
                    <button
                      type="button"
                      onClick={clearTemplate}
                      className="text-sm text-red-600 hover:text-red-800"
                    >
                      Clear
                    </button>
                  )}
                </div>
                {parameters.templatesRaw && (
                  <p className="text-xs text-green-600 mt-1">
                    Template loaded ({parameters.templatesRaw.length} chars)
                  </p>
                )}
              </div>
              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={parameters.relax_prediction}
                  onChange={(e) =>
                    setParameters((p) => ({ ...p, relax_prediction: e.target.checked }))
                  }
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 dark:border-gray-600"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Relax prediction (energy minimization, slower)
                </span>
              </label>
            </div>
          )}

          {/* Actions */}
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
              Predict Structure
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
