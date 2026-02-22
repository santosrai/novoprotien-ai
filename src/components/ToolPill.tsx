import React from 'react';
import { Wrench } from 'lucide-react';

const TOOL_LABELS: Record<string, string> = {
  open_alphafold_dialog: 'AlphaFold',
  open_openfold2_dialog: 'OpenFold2',
  open_rfdiffusion_dialog: 'RFdiffusion',
  open_proteinmpnn_dialog: 'ProteinMPNN',
  open_diffdock_dialog: 'DiffDock',
  search_uniprot: 'UniProt',
  show_smiles_in_viewer: 'SMILES 3D',
  validate_structure: 'Validation',
  mvs_builder: 'MVS Builder',
};

interface ToolPillProps {
  toolName: string;
  className?: string;
}

export const ToolPill: React.FC<ToolPillProps> = ({ toolName, className = '' }) => {
  const label = TOOL_LABELS[toolName] || toolName;

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700 ${className}`}
    >
      <Wrench className="w-3 h-3" />
      {label}
    </span>
  );
};
