import type { Message } from '../stores/chatHistoryStore';
import type { ValidationReport } from './validation';
import type { PipelineBlueprint } from '../components/pipeline-canvas';

export type { Message };

export interface ProteinLabel {
  id: string;
  user_id: string;
  session_id: string;
  short_label: string;
  kind: string;
  source_tool: string | null;
  file_id: string | null;
  job_id: string | null;
  metadata: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExtendedMessage extends Message {
  tokenUsage?: {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
  };
  diffdockResult?: {
    pdbContent?: string;
    filename?: string;
    job_id?: string;
    pdb_url?: string;
    message?: string;
  };
  validationResult?: ValidationReport;
  blueprint?: PipelineBlueprint;
  blueprintRationale?: string;
  blueprintApproved?: boolean;
  alignmentResult?: {
    structure1: { pdbContent: string; label: string };
    structure2: { pdbContent: string; label: string };
  };
  af2bindResult?: {
    targetId: string;
    chain: string;
    pdbContent: string;
    residues: Array<{ chain: string; resi: number; resn: string; pBind: number }>;
    topResidues: Array<{ chain: string; resi: number; resn: string; pBind: number }>;
    computeTime: number;
    totalResidues: number;
  };
}

export interface FileUploadState {
  file: File;
  status: 'uploading' | 'uploaded' | 'error';
  fileInfo?: {
    file_id: string;
    filename: string;
    file_url: string;
    atoms: number;
    chains: string[];
    size: number;
    chain_residue_counts?: Record<string, number>;
    total_residues?: number;
  };
  error?: string;
}
