import React from 'react';
import { Download, Play } from 'lucide-react';
import type { ExtendedMessage } from '../../../types/chat';

interface Props {
  result: ExtendedMessage['diffdockResult'];
  plugin: any;
  onLoadInViewer: () => void;
}

const DiffDockResultCard: React.FC<Props> = ({ result, plugin, onLoadInViewer }) => {
  if (!result?.pdbContent && !result?.pdb_url) return null;

  const downloadPDB = () => {
    if (result.pdbContent) {
      const blob = new Blob([result.pdbContent], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = result.filename || 'diffdock_result.pdb';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } else if (result.pdb_url) {
      window.open(result.pdb_url, '_blank');
    }
  };

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-teal-50 to-cyan-50 border border-teal-200 rounded-lg dark:from-teal-900/20 dark:to-cyan-900/20 dark:border-teal-700">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-teal-600 rounded-full flex items-center justify-center">
          <span className="text-white text-sm font-bold">DD</span>
        </div>
        <div>
          <h4 className="font-medium text-gray-900 dark:text-gray-100">DiffDock Protein-Ligand Docking</h4>
          <p className="text-xs text-gray-600 dark:text-gray-400">Docking completed successfully</p>
        </div>
      </div>
      <div className="flex space-x-2">
        <button
          onClick={downloadPDB}
          className="flex items-center space-x-1 px-3 py-2 bg-teal-600 text-white rounded-md hover:bg-teal-700 text-sm"
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

export default DiffDockResultCard;
