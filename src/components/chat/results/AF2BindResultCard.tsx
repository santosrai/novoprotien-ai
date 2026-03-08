import React, { useState } from 'react';
import { Crosshair, Play, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import type { ExtendedMessage } from '../../../types/chat';

interface Props {
  result: NonNullable<ExtendedMessage['af2bindResult']>;
  onLoadInViewer: (result: NonNullable<ExtendedMessage['af2bindResult']>) => Promise<void>;
}

const getPBindColor = (p: number): string => {
  if (p >= 0.75) return 'text-blue-700';
  if (p >= 0.5) return 'text-blue-500';
  if (p >= 0.25) return 'text-gray-500';
  return 'text-red-400';
};

const getPBindBg = (p: number): string => {
  if (p >= 0.75) return 'bg-blue-600';
  if (p >= 0.5) return 'bg-blue-400';
  if (p >= 0.25) return 'bg-gray-300';
  return 'bg-red-300';
};

const AF2BindResultCard: React.FC<Props> = ({ result, onLoadInViewer }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const handleVisualize = async () => {
    setIsLoading(true);
    try {
      await onLoadInViewer(result);
      setLoaded(true);
    } catch (err) {
      console.error('[AF2Bind] Failed to load in viewer:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const highConfCount = result.residues.filter(r => r.pBind > 0.5).length;
  const displayResidues = showAll ? result.topResidues : result.topResidues.slice(0, 8);

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-red-50 via-white to-blue-50 border border-blue-200 rounded-lg">
      {/* Header */}
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
          <Crosshair className="w-4 h-4 text-white" />
        </div>
        <div>
          <h4 className="font-medium text-gray-900">AF2Bind Binding Site Prediction</h4>
          <p className="text-xs text-gray-600">
            Target: <span className="font-medium text-blue-700">{result.targetId}</span>
            {' '} chain {result.chain}
            {' | '}{result.totalResidues} residues
            {' | '}{result.computeTime.toFixed(1)}s
          </p>
        </div>
      </div>

      {/* Summary stats */}
      <div className="mb-3 grid grid-cols-3 gap-2 text-xs">
        <div className="bg-white rounded p-2 text-center border border-gray-100">
          <div className="text-lg font-bold text-gray-800">{result.totalResidues}</div>
          <div className="text-gray-500">Total residues</div>
        </div>
        <div className="bg-white rounded p-2 text-center border border-gray-100">
          <div className="text-lg font-bold text-blue-600">{highConfCount}</div>
          <div className="text-gray-500">p(bind) &gt; 0.5</div>
        </div>
        <div className="bg-white rounded p-2 text-center border border-gray-100">
          <div className="text-lg font-bold text-gray-600">{result.computeTime.toFixed(1)}s</div>
          <div className="text-gray-500">Compute time</div>
        </div>
      </div>

      {/* Top residues table */}
      {result.topResidues.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-medium text-gray-600 mb-1">Top binding residues:</div>
          <div className="bg-white rounded border border-gray-100 overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 text-gray-500">
                  <th className="px-2 py-1 text-left">#</th>
                  <th className="px-2 py-1 text-left">Residue</th>
                  <th className="px-2 py-1 text-left">Chain</th>
                  <th className="px-2 py-1 text-right">p(bind)</th>
                  <th className="px-2 py-1 w-20"></th>
                </tr>
              </thead>
              <tbody>
                {displayResidues.map((r, i) => (
                  <tr key={`${r.chain}-${r.resi}`} className="border-t border-gray-50">
                    <td className="px-2 py-1 text-gray-400">{i + 1}</td>
                    <td className="px-2 py-1 font-medium">
                      {r.resn}<span className="text-gray-400">{r.resi}</span>
                    </td>
                    <td className="px-2 py-1 text-gray-500">{r.chain}</td>
                    <td className={`px-2 py-1 text-right font-mono font-medium ${getPBindColor(r.pBind)}`}>
                      {r.pBind.toFixed(3)}
                    </td>
                    <td className="px-2 py-1">
                      <div className="w-full bg-gray-100 rounded-full h-1.5">
                        <div
                          className={`h-1.5 rounded-full ${getPBindBg(r.pBind)}`}
                          style={{ width: `${Math.min(r.pBind * 100, 100)}%` }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {result.topResidues.length > 8 && (
              <button
                onClick={() => setShowAll(!showAll)}
                className="w-full py-1 text-xs text-blue-600 hover:bg-blue-50 flex items-center justify-center space-x-1"
              >
                {showAll ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                <span>{showAll ? 'Show less' : `Show all ${result.topResidues.length}`}</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Visualize button */}
      <div className="flex space-x-2">
        <button
          onClick={handleVisualize}
          disabled={isLoading}
          className="flex items-center space-x-1 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          <span>{loaded ? 'Reload in 3D' : 'Visualize in 3D'}</span>
        </button>
      </div>

      {loaded && (
        <p className="mt-2 text-[10px] text-gray-400">
          Colored by binding probability: red = low, white = medium, blue = high. B-factors encode p(bind) x 100.
        </p>
      )}
    </div>
  );
};

export default AF2BindResultCard;
