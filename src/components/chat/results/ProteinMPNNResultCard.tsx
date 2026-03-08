import React from 'react';
import { Download, Copy } from 'lucide-react';
import type { ExtendedMessage } from '../../../types/chat';

interface Props {
  result: ExtendedMessage['proteinmpnnResult'];
}

const ProteinMPNNResultCard: React.FC<Props> = ({ result }) => {
  if (!result) return null;

  const copySequence = async (sequence: string) => {
    try {
      await navigator.clipboard.writeText(sequence);
      console.log('[ProteinMPNN] Sequence copied to clipboard');
    } catch (err) {
      console.warn('Failed to copy sequence', err);
    }
  };

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-emerald-50 to-teal-50 border border-emerald-200 rounded-lg">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-emerald-600 rounded-full flex items-center justify-center">
          <span className="text-white text-sm font-bold">PM</span>
        </div>
        <div>
          <h4 className="font-medium text-gray-900">ProteinMPNN Sequence Design</h4>
          <p className="text-xs text-gray-600">
            Job {result.jobId} • {result.sequences.length} sequence{result.sequences.length === 1 ? '' : 's'}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-3">
        <a
          href={result.downloads.json}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center space-x-1 px-3 py-1 text-xs bg-emerald-100 text-emerald-700 rounded-full hover:bg-emerald-200"
        >
          <Download className="w-3 h-3" />
          <span>JSON</span>
        </a>
        <a
          href={result.downloads.fasta}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center space-x-1 px-3 py-1 text-xs bg-emerald-100 text-emerald-700 rounded-full hover:bg-emerald-200"
        >
          <Download className="w-3 h-3" />
          <span>FASTA</span>
        </a>
        {result.downloads.raw && (
          <a
            href={result.downloads.raw}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center space-x-1 px-3 py-1 text-xs bg-emerald-100 text-emerald-700 rounded-full hover:bg-emerald-200"
          >
            <Download className="w-3 h-3" />
            <span>Raw data</span>
          </a>
        )}
      </div>

      <div className="space-y-4">
        {result.sequences.map((seq, index) => (
          <div key={seq.id} className="border border-emerald-200 rounded-lg bg-white">
            <div className="flex items-center justify-between px-3 py-2 border-b border-emerald-100 bg-emerald-50">
              <div>
                <p className="text-sm font-medium text-emerald-800">Design {index + 1}</p>
                <p className="text-xs text-emerald-600">{seq.length} residues</p>
              </div>
              <button
                onClick={() => copySequence(seq.sequence)}
                className="inline-flex items-center space-x-1 text-xs text-emerald-700 hover:text-emerald-900"
                title="Copy sequence"
              >
                <Copy className="w-3 h-3" />
                <span>Copy</span>
              </button>
            </div>
            <div className="px-3 py-3">
              <pre className="text-xs font-mono whitespace-pre-wrap break-words bg-emerald-50 border border-emerald-100 rounded p-3">{seq.sequence}</pre>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProteinMPNNResultCard;
