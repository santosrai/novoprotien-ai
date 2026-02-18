import React from 'react';

/**
 * Horizontal pLDDT / confidence score scale panel.
 * Shown below the MolStar viewer when the structure is from AlphaFold or OpenFold2.
 */
export const ConfidenceScorePanel: React.FC = () => {
  const gradient = 'linear-gradient(to right, #7e22ce 0%, #2563eb 25%, #0d9488 50%, #22c55e 75%, #eab308 100%)';
  const ticks = [0, 50, 70, 90, 100];

  return (
    <div className="px-4 py-3 bg-gray-800 border-t border-gray-700 flex flex-col gap-1.5">
      <div className="text-xs font-medium text-gray-300">Prediction Score (pLDDT)</div>
      <div className="flex flex-col gap-0.5">
        <div
          className="w-full h-5 rounded overflow-hidden border border-gray-600"
          style={{ background: gradient }}
          role="img"
          aria-label="pLDDT scale from 0 to 100"
        />
        <div className="flex justify-between text-xs text-gray-400 w-full">
          {ticks.map((t) => (
            <span key={t}>{t}</span>
          ))}
        </div>
      </div>
    </div>
  );
};
