import { useMutation } from '@tanstack/react-query';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../../utils/api';

export interface DiffDockParameters {
  num_poses?: number;
  time_divisions?: number;
  steps?: number;
  save_trajectory?: boolean;
  is_staged?: boolean;
}

export interface DiffDockPredictParams {
  protein_file_id?: string;
  protein_content?: string;
  ligand_sdf_content: string;
  parameters?: DiffDockParameters;
  job_id?: string;
  jobId?: string;
  session_id?: string;
  sessionId?: string;
}

export interface DiffDockPredictResponse {
  status: 'completed' | 'error';
  job_id?: string;
  pdb_url?: string;
  pdbContent?: string;
  message?: string;
  error?: string;
  errorCode?: string;
  userMessage?: string;
}

/**
 * Mutation hook for DiffDock protein-ligand docking (blocking).
 */
export function useDiffDockPredict() {
  const queryClient = useQueryClient();

  return useMutation<DiffDockPredictResponse, Error, DiffDockPredictParams>({
    mutationFn: async (params) => {
      const response = await api.post<DiffDockPredictResponse>('/diffdock/predict', {
        protein_file_id: params.protein_file_id,
        protein_content: params.protein_content,
        ligand_sdf_content: params.ligand_sdf_content,
        parameters: params.parameters ?? {},
        job_id: params.job_id ?? params.jobId,
        session_id: params.session_id ?? params.sessionId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
  });
}
