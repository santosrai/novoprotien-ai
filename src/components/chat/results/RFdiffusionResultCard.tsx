import React from 'react';
import { Download, Play } from 'lucide-react';
import type { ExtendedMessage } from '../../../types/chat';

interface Props {
  result: ExtendedMessage['rfdiffusionResult'];
  plugin: any;
  onLoadInViewer: () => void;
}

const RFdiffusionResultCard: React.FC<Props> = ({ result, plugin, onLoadInViewer }) => {
  if (!result?.pdbContent) return null;

  const downloadPDB = () => {
    const blob = new Blob([result.pdbContent!], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = result.filename || 'rfdiffusion_design.pdb';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-indigo-50 to-violet-50 border border-indigo-200 rounded-lg">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center">
          <span className="text-white text-sm font-bold">RF</span>
        </div>
        <div>
          <h4 className="font-medium text-gray-900">RFdiffusion Protein Design</h4>
          <p className="text-xs text-gray-600">Designed structure ready</p>
        </div>
      </div>
      <div className="flex space-x-2">
        <button
          onClick={downloadPDB}
          className="flex items-center space-x-1 px-3 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm"
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
      </div>
    </div>
  );
};

export default RFdiffusionResultCard;
