import React from 'react';
import { Tag } from 'lucide-react';
import type { ProteinLabel } from '../types/chat';
import ProteinLabelBadge from './ProteinLabelBadge';

interface Props {
  labels: ProteinLabel[];
  isLoading?: boolean;
}

const SOURCE_ICONS: Record<string, string> = {
  upload: 'PDB',
  RFdiffusion: 'RF',
  ProteinMPNN: 'PM',
  AlphaFold: 'AF',
  OpenFold2: 'OF',
  ESMFold: 'ES',
  DiffDock: 'DD',
};

const ProteinLabelPanel: React.FC<Props> = ({ labels, isLoading }) => {
  if (isLoading) {
    return (
      <div className="px-3 py-2 text-xs text-gray-400 flex items-center gap-1">
        <Tag className="w-3 h-3" />
        <span>Loading labels...</span>
      </div>
    );
  }

  if (!labels.length) return null;

  return (
    <div className="px-3 py-2 border-t border-gray-200 bg-gray-50">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Tag className="w-3 h-3 text-gray-400" />
        <span className="text-[10px] font-medium text-gray-500 uppercase tracking-wider">
          Proteins
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {labels.map((label) => (
          <div
            key={label.id}
            className="flex items-center gap-1 group"
            title={[
              label.short_label,
              label.kind,
              label.source_tool && `Source: ${label.source_tool}`,
              label.file_id && `File: ${label.file_id.slice(0, 8)}`,
            ].filter(Boolean).join(' | ')}
          >
            <ProteinLabelBadge label={label} size="md" />
            <span className="text-[10px] text-gray-400 hidden group-hover:inline">
              {SOURCE_ICONS[label.source_tool || ''] || label.kind}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProteinLabelPanel;
