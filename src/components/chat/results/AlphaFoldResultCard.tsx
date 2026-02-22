import React from 'react';
import { Download, Play, Shield } from 'lucide-react';
import type { ExtendedMessage } from '../../../types/chat';

interface Props {
  result: ExtendedMessage['alphafoldResult'];
  plugin: any;
  onLoadInViewer: (result: NonNullable<ExtendedMessage['alphafoldResult']>, message?: ExtendedMessage) => void;
  onValidate: (pdbContent: string) => void;
  message?: ExtendedMessage;
}

const AlphaFoldResultCard: React.FC<Props> = ({ result, plugin, onLoadInViewer, onValidate, message }) => {
  if (!result) return null;

  const downloadPDB = () => {
    if (result.pdbContent) {
      const blob = new Blob([result.pdbContent], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = result.filename || 'alphafold_result.pdb';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-purple-600 rounded-full flex items-center justify-center">
          <span className="text-white text-sm font-bold">AF</span>
        </div>
        <div>
          <h4 className="font-medium text-gray-900">AlphaFold2 Structure Prediction</h4>
          <p className="text-xs text-gray-600">
            {result.sequence ? `${result.sequence.length} residues` : 'Structure predicted'}
          </p>
        </div>
      </div>
      
      {result.metadata && (
        <div className="mb-3 text-xs text-gray-600">
          <div className="grid grid-cols-2 gap-2">
            {result.parameters?.algorithm && (
              <span>Algorithm: {result.parameters.algorithm}</span>
            )}
            {result.parameters?.databases && (
              <span>Databases: {result.parameters.databases.join(', ')}</span>
            )}
          </div>
        </div>
      )}
      
      <div className="flex space-x-2">
        <button
          onClick={downloadPDB}
          className="flex items-center space-x-1 px-3 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 text-sm"
        >
          <Download className="w-4 h-4" />
          <span>Download PDB</span>
        </button>
        
        <button
          onClick={() => onLoadInViewer(result, message)}
          disabled={!plugin}
          className="flex items-center space-x-1 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
        >
          <Play className="w-4 h-4" />
          <span>View 3D</span>
        </button>

        <button
          onClick={() => onValidate(result.pdbContent!)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-50 text-indigo-600 rounded-lg text-xs font-medium hover:bg-indigo-100 transition-colors"
          disabled={!result.pdbContent}
        >
          <Shield className="w-3.5 h-3.5" />
          Validate
        </button>
      </div>
    </div>
  );
};

export default AlphaFoldResultCard;
