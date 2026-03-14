import React, { useState } from 'react';
import { GitCompareArrows, Play, Loader2 } from 'lucide-react';
import type { ExtendedMessage } from '../../../types/chat';

interface AlignmentScores {
  rmsd: number;
  alignedLength: number;
  alignmentScore: number;
}

interface Props {
  result: NonNullable<ExtendedMessage['alignmentResult']>;
  onLoadInViewer: (result: NonNullable<ExtendedMessage['alignmentResult']>) => Promise<AlignmentScores | void>;
}

const AlignmentResultCard: React.FC<Props> = ({ result, onLoadInViewer }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [scores, setScores] = useState<AlignmentScores | null>(null);

  const handleCompare = async () => {
    setIsLoading(true);
    try {
      const alignResult = await onLoadInViewer(result);
      if (alignResult) {
        setScores(alignResult);
      }
    } catch (err) {
      console.error('[Alignment] Failed to load in viewer:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const getRmsdColor = (rmsd: number) => {
    if (rmsd <= 2.0) return 'text-green-600';
    if (rmsd <= 5.0) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getRmsdLabel = (rmsd: number) => {
    if (rmsd <= 2.0) return 'High similarity';
    if (rmsd <= 5.0) return 'Moderate';
    return 'Low similarity';
  };

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-indigo-50 to-orange-50 border border-indigo-200 rounded-lg">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center">
          <GitCompareArrows className="w-4 h-4 text-white" />
        </div>
        <div>
          <h4 className="font-medium text-gray-900">Structure Alignment</h4>
          <p className="text-xs text-gray-600">
            <span className="text-purple-600 font-medium">{result.structure1.label}</span>
            {' vs '}
            <span className="text-orange-600 font-medium">{result.structure2.label}</span>
          </p>
        </div>
      </div>

      {scores && (
        <div className="mb-3 grid grid-cols-3 gap-2 text-xs">
          <div className="bg-white rounded p-2 text-center border border-gray-100">
            <div className={`text-lg font-bold ${getRmsdColor(scores.rmsd)}`}>
              {scores.rmsd.toFixed(2)} &#xC5;
            </div>
            <div className="text-gray-500">RMSD</div>
            <div className={`text-[10px] ${getRmsdColor(scores.rmsd)}`}>
              {getRmsdLabel(scores.rmsd)}
            </div>
          </div>
          <div className="bg-white rounded p-2 text-center border border-gray-100">
            <div className="text-lg font-bold text-gray-800">
              {scores.alignedLength}
            </div>
            <div className="text-gray-500">Aligned atoms</div>
          </div>
          <div className="bg-white rounded p-2 text-center border border-gray-100">
            <div className="text-lg font-bold text-indigo-600">
              {scores.alignmentScore.toFixed(1)}
            </div>
            <div className="text-gray-500">Alignment score</div>
          </div>
        </div>
      )}

      <div className="flex space-x-2">
        <button
          onClick={handleCompare}
          disabled={isLoading}
          className="flex items-center space-x-1 px-3 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          <span>{scores ? 'Reload in 3D' : 'Compare in 3D'}</span>
        </button>
      </div>

      {scores && (
        <p className="mt-2 text-[10px] text-gray-400">
          Structures superposed via sequence alignment + RMSD minimization. Purple = {result.structure1.label}, Orange = {result.structure2.label}.
        </p>
      )}
    </div>
  );
};

export default AlignmentResultCard;
