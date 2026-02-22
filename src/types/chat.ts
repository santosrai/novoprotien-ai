import type { Message } from '../stores/chatHistoryStore';
import type { ValidationReport } from './validation';
import type { PipelineBlueprint } from '../components/pipeline-canvas';

export type { Message };

export interface ExtendedMessage extends Message {
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
