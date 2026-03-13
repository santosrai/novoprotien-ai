import React from 'react';
import type { ProteinLabel } from '../types/chat';

interface Props {
  label: ProteinLabel;
  size?: 'sm' | 'md';
}

const KIND_COLORS: Record<string, string> = {
  upload: 'bg-blue-100 text-blue-700 border-blue-200',
  design: 'bg-violet-100 text-violet-700 border-violet-200',
  folded: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  docked: 'bg-amber-100 text-amber-700 border-amber-200',
};

const ProteinLabelBadge: React.FC<Props> = ({ label, size = 'sm' }) => {
  const colorClass = KIND_COLORS[label.kind] || 'bg-gray-100 text-gray-700 border-gray-200';
  const sizeClass = size === 'sm'
    ? 'text-[10px] px-1.5 py-0.5'
    : 'text-xs px-2 py-0.5';

  return (
    <span
      className={`inline-flex items-center font-semibold rounded border ${colorClass} ${sizeClass}`}
      title={`${label.short_label} — ${label.kind}${label.source_tool ? ` (${label.source_tool})` : ''}`}
    >
      {label.short_label}
    </span>
  );
};

export default ProteinLabelBadge;
