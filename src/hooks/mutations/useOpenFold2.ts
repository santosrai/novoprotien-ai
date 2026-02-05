import { useMutation } from '@tanstack/react-query';
import { api } from '../../utils/api';

export interface OpenFold2PredictParams {
  sequence: string;
  alignments?: Record<string, unknown>;
  alignmentsRaw?: string;
  templates?: unknown;
  templatesRaw?: string;
  relax_prediction?: boolean;
  jobId: string;
  sessionId?: string;
}

export interface OpenFold2PredictResponse {
  status: 'completed' | 'error';
  job_id?: string;
  pdb_url?: string;
  pdbContent?: string;
  message?: string;
  error?: string;
  code?: string;
}

/**
 * Mutation hook for OpenFold2 structure prediction (blocking).
 */
export function useOpenFold2Predict() {
  return useMutation<OpenFold2PredictResponse, Error, OpenFold2PredictParams>({
    mutationFn: async (params) => {
      const response = await api.post<OpenFold2PredictResponse>('/openfold2/predict', {
        sequence: params.sequence,
        alignments: params.alignments,
        alignmentsRaw: params.alignmentsRaw,
        templates: params.templates,
        templatesRaw: params.templatesRaw,
        relax_prediction: params.relax_prediction ?? false,
        jobId: params.jobId,
        sessionId: params.sessionId,
      });
      return response.data;
    },
  });
}
