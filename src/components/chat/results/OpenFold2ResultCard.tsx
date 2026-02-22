import React from 'react';
import { Download, Play, Shield } from 'lucide-react';
import type { ExtendedMessage } from '../../../types/chat';

interface Props {
  result: ExtendedMessage['openfold2Result'];
  plugin: any;
  onLoadInViewer: () => void;
  onValidate: (pdbContent: string) => void;
}

const OpenFold2ResultCard: React.FC<Props> = ({ result, plugin, onLoadInViewer, onValidate }) => {
  if (!result?.pdbContent) return null;

  const downloadPDB = () => {
    const blob = new Blob([result.pdbContent!], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = result.filename || 'openfold2_result.pdb';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-lg">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-amber-600 rounded-full flex items-center justify-center">
          <span className="text-white text-sm font-bold">OF2</span>
        </div>
        <div>
          <h4 className="font-medium text-gray-900">OpenFold2 Structure Prediction</h4>
          <p className="text-xs text-gray-600">Structure predicted successfully</p>
        </div>
      </div>
      <div className="flex space-x-2">
        <button
          onClick={downloadPDB}
          className="flex items-center space-x-1 px-3 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 text-sm"
        >
          <Download className="w-4 h-4" />
          <span>Download PDB</span>
        </button>
        <button
          onClick={onLoadInViewer}
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

export default OpenFold2ResultCard;
