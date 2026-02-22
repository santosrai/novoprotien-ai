import React from 'react';
import { Download, Play } from 'lucide-react';
import type { ExtendedMessage } from '../../../types/chat';

interface Props {
  result: ExtendedMessage['smilesResult'];
  plugin: any;
  onLoadInViewer: () => void;
  onDownload: () => void;
}

const SmilesResultCard: React.FC<Props> = ({ result, plugin, onLoadInViewer, onDownload }) => {
  if (!result?.file_id || !result?.file_url) return null;

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-lg">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-emerald-600 rounded-full flex items-center justify-center">
          <span className="text-white text-sm font-bold">SM</span>
        </div>
        <div>
          <h4 className="font-medium text-gray-900">SMILES structure</h4>
          <p className="text-xs text-gray-600">{result.filename}</p>
        </div>
      </div>
      <div className="flex space-x-2">
        <button
          onClick={onDownload}
          className="flex items-center space-x-1 px-3 py-2 bg-emerald-600 text-white rounded-md hover:bg-emerald-700 text-sm"
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

export default SmilesResultCard;
