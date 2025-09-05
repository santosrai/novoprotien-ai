import React, { useState, useRef } from 'react';
import { Plus, Upload, X, FileText, Loader2, Paperclip, Trash2 } from 'lucide-react';

interface FileUploadResult {
  status: string;
  message: string;
  file_info: {
    filename: string;
    file_id: string;
    file_url: string;
    size: number;
    atoms: number;
    chains: string[];
  };
  agent_response?: any;
}

interface PDBFileUploadProps {
  onFileUploaded: (result: FileUploadResult) => void;
  onError: (error: string) => void;
  disabled?: boolean;
  currentFile?: {
    filename: string;
    file_id: string;
    file_path: string;
  } | null;
}

export const PDBFileUpload: React.FC<PDBFileUploadProps> = ({
  onFileUploaded,
  onError,
  disabled = false,
  currentFile = null
}) => {
  const [isUploading, setIsUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [showDialog, setShowDialog] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (file: File) => {
    if (!file) return;

    // Validate file type
    if (!file.name.toLowerCase().endsWith('.pdb')) {
      onError('Please select a PDB file (.pdb extension required)');
      return;
    }

    // Validate file size (10MB limit)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      onError('File too large. Maximum size is 10MB.');
      return;
    }

    setIsUploading(true);
    setShowDialog(false);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/upload/pdb', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const result: FileUploadResult = await response.json();
      onFileUploaded(result);
    } catch (error: any) {
      console.error('File upload failed:', error);
      onError(error.message || 'File upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
    // Reset input value to allow re-selecting the same file
    event.target.value = '';
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOver(false);
    
    const files = Array.from(event.dataTransfer.files);
    const pdbFile = files.find(f => f.name.toLowerCase().endsWith('.pdb'));
    
    if (pdbFile) {
      handleFileSelect(pdbFile);
    } else {
      onError('Please drop a PDB file (.pdb extension required)');
    }
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  if (isUploading) {
    return (
      <div className="flex items-center space-x-2 px-2 py-1 bg-blue-50 border border-blue-200 rounded-md">
        <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
        <span className="text-xs text-blue-700">Uploading...</span>
      </div>
    );
  }

  const clearFile = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    onFileUploaded({ 
      status: 'cleared', 
      message: '', 
      file_info: { filename: '', file_id: '', file_url: '', size: 0, atoms: 0, chains: [] } 
    });
  };

  const handleUploadClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setShowDialog(true);
  };

  return (
    <>
      {currentFile ? (
        // Show attached file with clear option
        <div className="flex items-center space-x-1 px-2 py-1 bg-green-50 border border-green-200 rounded-md">
          <Paperclip className="w-3 h-3 text-green-600" />
          <span className="text-xs text-green-700 max-w-20 truncate" title={currentFile.filename}>
            {currentFile.filename}
          </span>
          <button
            type="button"
            onClick={clearFile}
            disabled={disabled}
            className="p-0.5 hover:bg-green-100 rounded"
            title="Remove file"
          >
            <X className="w-3 h-3 text-green-600" />
          </button>
        </div>
      ) : (
        // Show upload button
        <button
          type="button"
          onClick={handleUploadClick}
          disabled={disabled}
          className="flex items-center justify-center w-8 h-8 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-full disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          title="Upload PDB file"
        >
          <Plus className="w-4 h-4 text-gray-600" />
        </button>
      )}

      {/* Upload Dialog */}
      {showDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Upload PDB File</h3>
              <button
                type="button"
                onClick={() => setShowDialog(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-4">
              {/* Drop Zone */}
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
                  dragOver
                    ? 'border-blue-400 bg-blue-50'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
              >
                <Upload className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                <p className="text-sm text-gray-600 mb-2">
                  Drag and drop your PDB file here, or click to browse
                </p>
                <p className="text-xs text-gray-500 mb-4">
                  Supports .pdb files up to 10MB
                </p>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <FileText className="w-4 h-4" />
                  <span>Choose File</span>
                </button>
              </div>

              {/* File Input */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdb"
                onChange={handleFileInputChange}
                className="hidden"
              />

              {/* Help Text */}
              <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                <h4 className="text-sm font-medium text-gray-900 mb-1">
                  About PDB Files
                </h4>
                <p className="text-xs text-gray-600">
                  PDB (Protein Data Bank) files contain 3D structural data for proteins, 
                  nucleic acids, and other molecules. Once uploaded, you can visualize 
                  the structure in 3D using the "View 3D" button.
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="flex justify-end space-x-2 p-4 border-t border-gray-200">
              <button
                type="button"
                onClick={() => setShowDialog(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};