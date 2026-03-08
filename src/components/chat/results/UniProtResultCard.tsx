import React from 'react';
import { Search, Eye, Download } from 'lucide-react';
import type { Message } from '../../../stores/chatHistoryStore';

interface Props {
  result: Message['uniprotSearchResult'];
  onFetchEntry: (accession: string) => void;
  onViewStructure: (pdbId: string) => void;
}

const UniProtResultCard: React.FC<Props> = ({ result, onFetchEntry, onViewStructure }) => {
  if (!result || !result.results?.length) return null;

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
          <Search className="w-4 h-4 text-white" />
        </div>
        <div>
          <h4 className="font-medium text-gray-900">UniProt Search Results</h4>
          <p className="text-xs text-gray-600">
            {result.count} result{result.count !== 1 ? 's' : ''} for &quot;{result.query}&quot;
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-blue-100/60">
              <th className="text-left px-2 py-1.5 font-semibold text-gray-700 border-b border-blue-200">Protein</th>
              <th className="text-left px-2 py-1.5 font-semibold text-gray-700 border-b border-blue-200">UniProt</th>
              <th className="text-left px-2 py-1.5 font-semibold text-gray-700 border-b border-blue-200">Sequence</th>
              <th className="text-left px-2 py-1.5 font-semibold text-gray-700 border-b border-blue-200">PDB</th>
              <th className="text-left px-2 py-1.5 font-semibold text-gray-700 border-b border-blue-200">Actions</th>
            </tr>
          </thead>
          <tbody>
            {result.results.map((entry) => (
              <tr key={entry.accession} className="hover:bg-blue-50/50 border-b border-blue-100 last:border-b-0">
                <td className="px-2 py-2 max-w-[160px]">
                  <div className="font-medium text-gray-900 truncate" title={entry.protein || entry.id}>
                    {entry.protein || entry.id}
                  </div>
                  <div className="text-[10px] text-gray-500 truncate" title={entry.organism || ''}>
                    {entry.organism || ''}
                  </div>
                </td>
                <td className="px-2 py-2">
                  <a
                    href={`https://www.uniprot.org/uniprotkb/${entry.accession}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline font-mono"
                  >
                    {entry.accession}
                  </a>
                  {entry.reviewed && (
                    <span className="ml-1 text-[9px] bg-amber-100 text-amber-700 px-1 rounded" title="Swiss-Prot reviewed">
                      R
                    </span>
                  )}
                </td>
                <td className="px-2 py-2 font-mono text-[10px] text-gray-600 max-w-[140px]">
                  <span className="truncate block" title={entry.sequence}>
                    {entry.sequence?.slice(0, 30)}{entry.sequence?.length > 30 ? '...' : ''}
                  </span>
                  {entry.length != null && (
                    <span className="text-[9px] text-gray-400">{entry.length} aa</span>
                  )}
                </td>
                <td className="px-2 py-2">
                  {entry.pdb_ids?.length > 0 ? (
                    <div className="flex flex-wrap gap-0.5">
                      {entry.pdb_ids.slice(0, 3).map((pdb) => (
                        <button
                          key={pdb}
                          onClick={() => onViewStructure(pdb)}
                          className="text-[10px] bg-emerald-100 text-emerald-700 px-1 rounded hover:bg-emerald-200 cursor-pointer"
                          title={`View ${pdb} in 3D`}
                        >
                          {pdb}
                        </button>
                      ))}
                      {entry.pdb_ids.length > 3 && (
                        <span className="text-[10px] text-gray-400">+{entry.pdb_ids.length - 3}</span>
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </td>
                <td className="px-2 py-2">
                  <div className="flex space-x-1">
                    <button
                      onClick={() => onFetchEntry(entry.accession)}
                      className="flex items-center space-x-0.5 px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-[10px]"
                      title="Fetch full details"
                    >
                      <Download className="w-3 h-3" />
                      <span>Fetch</span>
                    </button>
                    {entry.pdb_ids?.length > 0 && (
                      <button
                        onClick={() => onViewStructure(entry.pdb_ids[0])}
                        className="flex items-center space-x-0.5 px-2 py-1 bg-emerald-600 text-white rounded hover:bg-emerald-700 text-[10px]"
                        title="View 3D structure"
                      >
                        <Eye className="w-3 h-3" />
                        <span>3D</span>
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default UniProtResultCard;
