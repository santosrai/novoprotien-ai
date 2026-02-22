import { useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { api } from '../utils/api';
import { useChatHistoryStore } from '../stores/chatHistoryStore';
import { AlphaFoldErrorHandler, OpenFold2ErrorHandler, RFdiffusionErrorHandler, DiffDockErrorHandler } from '../utils/errorHandler';
import { logAlphaFoldError } from '../utils/errorLogger';
import { extractProteinMPNNSequences, createProteinMPNNError } from '../utils/chatHelpers';
import type { ExtendedMessage } from '../types/chat';

export interface UseJobHandlersParams {
  activeSession: { id: string; messages: any[] } | null;
  activeSessionId: string | null;
  addMessage: (msg: any) => void;
  updateMessages: (msgs: any[]) => void;
  alphafoldProgress: any;
  proteinmpnnProgress: any;
  diffdockPredictMutation: any;
  setShowAlphaFoldDialog: (v: boolean) => void;
  setShowOpenFold2Dialog: (v: boolean) => void;
  setShowDiffDockDialog: (v: boolean) => void;
  setShowRFdiffusionDialog: (v: boolean) => void;
  setShowProteinMPNNDialog: (v: boolean) => void;
}

export function useJobHandlers({
  activeSession,
  activeSessionId,
  addMessage,
  updateMessages,
  alphafoldProgress,
  proteinmpnnProgress,
  diffdockPredictMutation,
  setShowAlphaFoldDialog,
  setShowOpenFold2Dialog,
  setShowDiffDockDialog,
  setShowRFdiffusionDialog,
  setShowProteinMPNNDialog,
}: UseJobHandlersParams) {

  const updateMessageInSession = (sessionId: string, pendingMessageId: string, content: string, update: Record<string, any>) => {
    const store = useChatHistoryStore.getState();
    const session = store.sessions.find(s => s.id === sessionId);
    if (!session) return;
    const messages = session.messages || [];
    const idx = messages.findIndex(m => m.id === pendingMessageId);
    if (idx === -1) return;
    const updated = [...messages];
    updated[idx] = { ...updated[idx], content, ...update };
    updateMessages(updated);
  };

  const handleAlphaFoldConfirm = async (sequence: string, parameters: any) => {
    console.log('🚀 [AlphaFold] User confirmed folding request');
    console.log('📊 [AlphaFold] Sequence length:', sequence.length);
    console.log('⚙️ [AlphaFold] Parameters:', parameters);
    
    setShowAlphaFoldDialog(false);
    
    const jobId = `af_${Date.now()}`;
    console.log('🆔 [AlphaFold] Generated job ID:', jobId);
    
    const validationError = AlphaFoldErrorHandler.handleSequenceValidation(sequence, jobId);
    if (validationError) {
      logAlphaFoldError(validationError, { sequence: sequence.slice(0, 100), parameters });
      
      const errorMessage: ExtendedMessage = {
        id: (Date.now() + 1).toString(),
        content: validationError.userMessage,
        type: 'ai',
        timestamp: new Date(),
        error: validationError
      };
      addMessage(errorMessage);
      return;
    }
    
    alphafoldProgress.startProgress(jobId, 'Submitting protein folding request...');
    console.log('📡 [AlphaFold] Starting progress tracking for job:', jobId);

    const pendingMessageId = uuidv4();
    const pendingMessage: ExtendedMessage = {
      id: pendingMessageId,
      content: 'AlphaFold structure prediction in progress...',
      type: 'ai',
      timestamp: new Date(),
    };
    addMessage(pendingMessage);

    const sessionId = activeSession?.id;

    const updateAlphaFoldMessage = (content: string, update: Partial<ExtendedMessage>) => {
      if (!sessionId) return;
      updateMessageInSession(sessionId, pendingMessageId, content, update);
    };

    try {
      console.log('🌐 [AlphaFold] Making API call to /api/alphafold/fold');
      console.log('📦 [AlphaFold] Payload:', { sequence: sequence.slice(0, 50) + '...', parameters, jobId });
      
      const response = await api.post('/alphafold/fold', {
        sequence,
        parameters,
        jobId
      });
      
      console.log('📨 [AlphaFold] API response received:', response.status, response.data);

      if (response.status === 202 || response.data.status === 'accepted' || response.data.status === 'queued' || response.data.status === 'running') {
        console.log('🕒 [AlphaFold] Job accepted, starting polling for status...', { jobId });
        const start = Date.now();
        const poll = async () => {
          try {
            const statusResp = await api.get(`/alphafold/status/${jobId}`);
            const st = statusResp.data?.status;
            if (st === 'completed') {
              const result = statusResp.data?.data || {};
              updateAlphaFoldMessage(
                `AlphaFold2 structure prediction completed successfully! The folded structure is ready for download and visualization.`,
                {
                  alphafoldResult: {
                    pdbContent: result.pdbContent,
                    filename: result.filename || `folded_${Date.now()}.pdb`,
                    sequence,
                    parameters,
                    metadata: result.metadata
                  }
                }
              );
              alphafoldProgress.completeProgress();
              return true;
            } else if (st === 'error' || st === 'not_found') {
              const errorMsg = st === 'not_found'
                ? 'Job not found. The server may have been restarted. Please try submitting again.'
                : statusResp.data?.error || 'Folding computation failed';
              const apiError = AlphaFoldErrorHandler.createError(
                'FOLDING_FAILED',
                { jobId, sequenceLength: sequence.length, parameters },
                errorMsg,
                undefined,
                jobId
              );
              logAlphaFoldError(apiError, { apiResponse: statusResp.data, sequence: sequence.slice(0, 100), parameters });
              updateAlphaFoldMessage(apiError.userMessage, { error: apiError });
              alphafoldProgress.errorProgress(apiError.userMessage);
              return true;
            } else if (st === 'cancelled') {
              updateAlphaFoldMessage('Folding was cancelled.', {});
              alphafoldProgress.cancelProgress();
              return true;
            } else {
              const elapsed = (Date.now() - start) / 1000;
              const estDuration = 300;
              const pct = Math.min(90, Math.round((elapsed / estDuration) * 90));
              alphafoldProgress.updateProgress(`Processing... (${Math.round(elapsed)}s)`, pct);
              return false;
            }
          } catch (e: unknown) {
            const status = (e as { response?: { status?: number } })?.response?.status;
            const terminalStatuses = [400, 401, 403, 404, 410];
            if (typeof status === 'number' && terminalStatuses.includes(status)) {
              const errorMsg = status === 404
                ? 'Job not found. The folding job may have expired or the server was restarted.'
                : `Request failed (HTTP ${status}). Please try submitting again.`;
              const apiError = AlphaFoldErrorHandler.createError(
                'FOLDING_FAILED',
                { jobId, sequenceLength: sequence.length, parameters },
                errorMsg,
                undefined,
                jobId
              );
              logAlphaFoldError(apiError, { httpStatus: status, sequence: sequence.slice(0, 100), parameters });
              updateAlphaFoldMessage(apiError.userMessage, { error: apiError });
              alphafoldProgress.errorProgress(apiError.userMessage);
              return true;
            }
            console.warn('⚠️ [AlphaFold] Polling failed, will retry...', e);
            return false;
          }
        };

        const timeoutSec = 45 * 60;
        let finished = false;
        while (!finished && (Date.now() - start) / 1000 < timeoutSec) {
          // eslint-disable-next-line no-await-in-loop
          finished = await poll();
          if (finished) break;
          // eslint-disable-next-line no-await-in-loop
          await new Promise(res => setTimeout(res, 3000));
        }

        if (!finished) {
          const msg = 'AlphaFold is still running past 45 minutes. It may finish soon; you can cancel and retry later.';
          const apiError = AlphaFoldErrorHandler.createError(
            'FOLDING_FAILED',
            { jobId, sequenceLength: sequence.length, parameters },
            msg,
            undefined,
            jobId
          );
          logAlphaFoldError(apiError, { sequence: sequence.slice(0, 100), parameters, timedOut: true });
          updateAlphaFoldMessage(apiError.userMessage, { error: apiError });
          alphafoldProgress.errorProgress(apiError.userMessage);
        }
        return;
      }

      if (response.data.status === 'success') {
        const result = response.data.data;
        updateAlphaFoldMessage(
          `AlphaFold2 structure prediction completed successfully! The folded structure is ready for download and visualization.`,
          {
            alphafoldResult: {
              pdbContent: result.pdbContent,
              filename: result.filename || `folded_${Date.now()}.pdb`,
              sequence,
              parameters,
              metadata: result.metadata
            }
          }
        );
        alphafoldProgress.completeProgress();
      } else {
        const apiError = AlphaFoldErrorHandler.createError(
          'FOLDING_FAILED',
          { jobId, sequenceLength: sequence.length, parameters },
          response.data.error || 'Folding computation failed',
          undefined,
          jobId
        );
        logAlphaFoldError(apiError, { apiResponse: response.data, sequence: sequence.slice(0, 100), parameters });
        updateAlphaFoldMessage(apiError.userMessage, { error: apiError });
        alphafoldProgress.errorProgress(apiError.userMessage);
      }
    } catch (error: any) {
      console.error('AlphaFold request failed:', error);
      const structuredError = AlphaFoldErrorHandler.handleAPIError(error, jobId);
      logAlphaFoldError(structuredError, { originalError: error.message, sequence: sequence.slice(0, 100), parameters, networkError: true });
      updateAlphaFoldMessage(structuredError.userMessage, { error: structuredError });
      alphafoldProgress.errorProgress(structuredError.userMessage);
    }
  };

  const handleOpenFold2Confirm = async (sequence: string, parameters: { alignmentsRaw?: string; templatesRaw?: string; relax_prediction: boolean }) => {
    setShowOpenFold2Dialog(false);
    const jobId = `of2_${Date.now()}`;
    const validationError = OpenFold2ErrorHandler.handleSequenceValidation(sequence, jobId);
    if (validationError) {
      addMessage({
        id: (Date.now() + 1).toString(),
        content: validationError.userMessage,
        type: 'ai',
        timestamp: new Date(),
        error: validationError,
      });
      return;
    }
    const pendingMessageId = uuidv4();
    const pendingMessage: ExtendedMessage = {
      id: pendingMessageId,
      content: 'OpenFold2 structure prediction in progress...',
      type: 'ai',
      timestamp: new Date(),
    };
    addMessage(pendingMessage);

    const sessionId = activeSession?.id;
    const updateOpenFold2Message = (content: string, update: Partial<ExtendedMessage>) => {
      if (!sessionId) return;
      updateMessageInSession(sessionId, pendingMessageId, content, update);
    };

    try {
      const response = await api.post('/openfold2/predict', {
        sequence,
        alignmentsRaw: parameters.alignmentsRaw,
        templatesRaw: parameters.templatesRaw,
        relax_prediction: parameters.relax_prediction ?? false,
        jobId,
        sessionId: activeSessionId ?? undefined,
      });
      const data = response.data;
      if (data.status === 'completed' && data.pdbContent) {
        updateOpenFold2Message(
          'OpenFold2 structure prediction completed successfully! The structure is ready for visualization.',
          {
            openfold2Result: {
              pdbContent: data.pdbContent,
              filename: data.filename || `openfold2_${jobId}.pdb`,
              job_id: data.job_id,
              pdb_url: data.pdb_url ?? (data.job_id ? `/api/openfold2/result/${data.job_id}` : undefined),
              message: data.message,
            },
          }
        );
      } else {
        const err = OpenFold2ErrorHandler.createError(data.code || 'API_ERROR', { jobId, feature: 'OpenFold2' }, data.error);
        updateOpenFold2Message(err.userMessage, { error: err });
      }
    } catch (error: any) {
      const err = OpenFold2ErrorHandler.createError('API_ERROR', { jobId, feature: 'OpenFold2' }, error?.response?.data?.error || error?.message);
      updateOpenFold2Message(err.userMessage, { error: err });
    }
  };

  const handleDiffDockClose = useCallback(() => {
    setShowDiffDockDialog(false);
    addMessage({
      id: uuidv4(),
      content: "You've closed the DiffDock dialog. Ask to dock a ligand when you're ready.",
      type: 'ai',
      timestamp: new Date(),
    });
  }, [addMessage, setShowDiffDockDialog]);

  const handleDiffDockConfirm = async (params: {
    protein_file_id?: string;
    protein_content?: string;
    ligand_sdf_content: string;
    parameters: { num_poses?: number; time_divisions?: number; steps?: number; save_trajectory?: boolean; is_staged?: boolean };
  }) => {
    setShowDiffDockDialog(false);
    const jobId = `diffdock_${Date.now()}`;
    const pendingMessageId = uuidv4();
    const pendingMessage: ExtendedMessage = {
      id: pendingMessageId,
      content: 'DiffDock docking in progress...',
      type: 'ai',
      timestamp: new Date(),
    };
    addMessage(pendingMessage);

    const sessionId = activeSession?.id;
    const updateDiffDockMessage = (content: string, update: Partial<ExtendedMessage>) => {
      if (!sessionId) return;
      updateMessageInSession(sessionId, pendingMessageId, content, update);
    };

    try {
      const data = await diffdockPredictMutation.mutateAsync({
        protein_file_id: params.protein_file_id,
        protein_content: params.protein_content,
        ligand_sdf_content: params.ligand_sdf_content,
        parameters: params.parameters ?? {},
        job_id: jobId,
        jobId,
        session_id: activeSessionId ?? undefined,
        sessionId: activeSessionId ?? undefined,
      });
      if (data.status === 'completed' && (data.pdbContent || data.pdb_url)) {
        updateDiffDockMessage(
          data.message ?? 'DiffDock docking completed successfully! The structure is ready for visualization.',
          {
            diffdockResult: {
              pdbContent: data.pdbContent,
              filename: data.job_id ? `diffdock_${data.job_id}.pdb` : 'diffdock_result.pdb',
              job_id: data.job_id,
              pdb_url: data.pdb_url ?? (data.job_id ? `/api/diffdock/result/${data.job_id}` : undefined),
              message: data.message,
            },
          }
        );
      } else {
        const err = DiffDockErrorHandler.handleError(
          { data: { errorCode: data.errorCode, userMessage: data.userMessage }, status: 400 },
          { jobId, feature: 'DiffDock' }
        );
        updateDiffDockMessage(err.userMessage, { error: err });
      }
    } catch (error: any) {
      const err = DiffDockErrorHandler.handleError(
        error?.response ?? { data: error?.response?.data, status: error?.response?.status },
        { jobId, feature: 'DiffDock' }
      );
      updateDiffDockMessage(err.userMessage, { error: err });
    }
  };

  const handleProteinMPNNConfirm = async (config: {
    pdbSource: 'rfdiffusion' | 'upload' | 'inline';
    sourceJobId?: string;
    uploadId?: string;
    parameters: any;
    message?: string;
  }) => {
    console.log('🧩 [ProteinMPNN] Confirm payload:', config);
    setShowProteinMPNNDialog(false);

    const jobId = `pm_${Date.now()}`;

    const payload = {
      jobId,
      pdbSource: config.pdbSource,
      sourceJobId: config.sourceJobId,
      uploadId: config.uploadId,
      parameters: config.parameters,
    };

    const context = {
      jobId,
      pdbSource: config.pdbSource,
      sourceJobId: config.sourceJobId,
      uploadId: config.uploadId,
      parameters: config.parameters,
    };

    const pendingMessageId = uuidv4();
    const pendingMessage: ExtendedMessage = {
      id: pendingMessageId,
      content: 'ProteinMPNN sequence design in progress...',
      type: 'ai',
      timestamp: new Date(),
    };
    addMessage(pendingMessage);

    const sessionId = activeSession?.id;
    const updateProteinMPNNMessage = (content: string, update: Partial<ExtendedMessage>) => {
      if (!sessionId) return;
      updateMessageInSession(sessionId, pendingMessageId, content, update);
    };

    try {
      proteinmpnnProgress.startProgress(jobId, 'Submitting ProteinMPNN design request...');
      const response = await api.post('/proteinmpnn/design', payload);
      console.log('🧬 [ProteinMPNN] Submission response:', response.status, response.data);

      if (response.status !== 202) {
        const errorDetails = createProteinMPNNError(
          'PROTEINMPNN_SUBMIT_FAILED',
          'ProteinMPNN job submission failed.',
          response.data?.error || 'Unexpected response from ProteinMPNN submission endpoint.',
          context,
        );
        updateProteinMPNNMessage(errorDetails.userMessage, { error: errorDetails });
        proteinmpnnProgress.errorProgress(errorDetails.userMessage);
        return;
      }

      const started = Date.now();
      const timeoutSec = 15 * 60;
      let finished = false;
      let lastProgressUpdate = 10;

      const poll = async (): Promise<boolean> => {
        if (proteinmpnnProgress.isCancelled?.()) {
          return true;
        }
        try {
          const statusResp = await api.get(`/proteinmpnn/status/${jobId}`);
          const statusData = statusResp.data || {};
          const status = statusData.status as string;
          const progressState = statusData.progress;

          console.log('⏱️ [ProteinMPNN] Poll status:', status, progressState);

          if (status === 'completed') {
            const resultResp = await api.get(`/proteinmpnn/result/${jobId}`);
            const resultData = resultResp.data || {};
            const sequences = extractProteinMPNNSequences(resultData);

            const sequenceEntries = sequences.map((sequence, idx) => ({
              id: `${jobId}_${idx + 1}`,
              sequence,
              length: sequence.length,
            }));

            const messageContent = sequenceEntries.length
              ? `ProteinMPNN generated ${sequenceEntries.length} candidate sequence${sequenceEntries.length === 1 ? '' : 's'}.`
              : 'ProteinMPNN job completed, but no sequences were returned.';

            updateProteinMPNNMessage(messageContent, {
              proteinmpnnResult: {
                jobId,
                sequences: sequenceEntries,
                downloads: {
                  json: `/api/proteinmpnn/result/${jobId}?fmt=json`,
                  fasta: `/api/proteinmpnn/result/${jobId}?fmt=fasta`,
                  raw: `/api/proteinmpnn/result/${jobId}?fmt=raw`,
                },
                metadata: resultData,
              },
            });
            proteinmpnnProgress.completeProgress(
              sequenceEntries.length ? 'Sequence design completed successfully!' : 'ProteinMPNN job completed.'
            );
            return true;
          }

          if (status === 'error' || status === 'timeout' || status === 'polling_failed') {
            const errorDetails = createProteinMPNNError(
              'PROTEINMPNN_JOB_FAILED',
              'ProteinMPNN sequence design failed.',
              statusData.error || status || 'Job failed',
              { ...context, status },
            );
            updateProteinMPNNMessage(errorDetails.userMessage, { error: errorDetails });
            proteinmpnnProgress.errorProgress(errorDetails.userMessage);
            return true;
          }

          if (status === 'not_found') {
            proteinmpnnProgress.updateProgress('Waiting for ProteinMPNN job to register...', lastProgressUpdate);
            return false;
          }

          const elapsedSeconds = (Date.now() - started) / 1000;
          const computedProgress = Math.min(95, Math.round((elapsedSeconds / timeoutSec) * 90));
          const progressValue = typeof progressState?.progress === 'number'
            ? progressState.progress
            : computedProgress;
          lastProgressUpdate = progressValue;
          const progressMessage = progressState?.message || 'Design in progress...';
          proteinmpnnProgress.updateProgress(progressMessage, progressValue);
          return false;
        } catch (pollError: any) {
          console.warn('⚠️ [ProteinMPNN] Polling error:', pollError);
          const elapsedSeconds = (Date.now() - started) / 1000;
          const fallbackProgress = Math.min(90, Math.round((elapsedSeconds / timeoutSec) * 80));
          proteinmpnnProgress.updateProgress('Waiting for ProteinMPNN result...', fallbackProgress);
          return false;
        }
      };

      while (!finished && (Date.now() - started) / 1000 < timeoutSec) {
        if (proteinmpnnProgress.isCancelled?.()) {
          finished = true;
          break;
        }
        // eslint-disable-next-line no-await-in-loop
        finished = await poll();
        if (finished) break;
        if (proteinmpnnProgress.isCancelled?.()) {
          finished = true;
          break;
        }
        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve) => setTimeout(resolve, 4000));
      }

      if (!finished && !proteinmpnnProgress.isCancelled?.()) {
        const errorDetails = createProteinMPNNError(
          'PROTEINMPNN_TIMEOUT',
          'ProteinMPNN job timed out before completion.',
          'Job exceeded client-side timeout threshold.',
          context,
        );
        updateProteinMPNNMessage(errorDetails.userMessage, { error: errorDetails });
        proteinmpnnProgress.errorProgress(errorDetails.userMessage);
      }
    } catch (error: any) {
      console.error('❌ [ProteinMPNN] Request failed:', error);
      const technicalMessage = error?.response?.data?.error || error?.message || 'Unknown ProteinMPNN error';
      const errorDetails = createProteinMPNNError(
        'PROTEINMPNN_REQUEST_FAILED',
        'Unable to submit ProteinMPNN job.',
        technicalMessage,
        context,
      );
      updateProteinMPNNMessage(errorDetails.userMessage, { error: errorDetails });
      proteinmpnnProgress.errorProgress(errorDetails.userMessage);
    }
  };

  const handleRFdiffusionConfirm = async (parameters: any) => {
    setShowRFdiffusionDialog(false);
    const jobId = `rf_${Date.now()}`;
    const pendingMessageId = uuidv4();
    const pendingMessage: ExtendedMessage = {
      id: pendingMessageId,
      content: 'RFdiffusion protein design in progress...',
      type: 'ai',
      timestamp: new Date(),
      jobId,
      jobType: 'rfdiffusion'
    };
    addMessage(pendingMessage);

    const sessionId = activeSession?.id;
    const updateRFdiffusionMessage = (content: string, update: Partial<ExtendedMessage>) => {
      if (!sessionId) return;
      updateMessageInSession(sessionId, pendingMessageId, content, { ...update, jobId: undefined, jobType: undefined });
    };

    try {
      const response = await api.post('/rfdiffusion/design', { parameters, jobId });

      if (response.data.status === 'success') {
        const result = response.data.data;
        updateRFdiffusionMessage(
          `RFdiffusion protein design completed successfully! The designed structure is ready for download and visualization.`,
          {
            rfdiffusionResult: {
              pdbContent: result.pdbContent,
              filename: result.filename || `designed_${Date.now()}.pdb`,
              parameters,
              metadata: result.metadata
            }
          }
        );
      } else {
        const apiError = RFdiffusionErrorHandler.handleError(response.data, { jobId, parameters, feature: 'RFdiffusion' });
        const displayContent = apiError.aiSummary || apiError.userMessage;
        updateRFdiffusionMessage(displayContent, { error: apiError });
      }
    } catch (error: any) {
      console.error('RFdiffusion request failed:', error);
      const structuredError = RFdiffusionErrorHandler.handleError(error, { jobId, parameters, feature: 'RFdiffusion' });
      const displayContent = structuredError.aiSummary || structuredError.userMessage;
      updateRFdiffusionMessage(displayContent, { error: structuredError });
    }
  };

  const handleAlphaFoldClose = useCallback(() => {
    setShowAlphaFoldDialog(false);
    addMessage({
      id: uuidv4(),
      content: "You've cancelled the folding. What else can I help you with?",
      type: 'ai',
      timestamp: new Date(),
    });
  }, [addMessage, setShowAlphaFoldDialog]);

  const handleRFdiffusionClose = useCallback(() => {
    setShowRFdiffusionDialog(false);
    addMessage({
      id: uuidv4(),
      content: "You've cancelled the design. What else can I help you with?",
      type: 'ai',
      timestamp: new Date(),
    });
  }, [addMessage, setShowRFdiffusionDialog]);

  const handleProteinMPNNClose = useCallback(() => {
    setShowProteinMPNNDialog(false);
    addMessage({
      id: uuidv4(),
      content: "You've cancelled the sequence design. What else can I help you with?",
      type: 'ai',
      timestamp: new Date(),
    });
  }, [addMessage, setShowProteinMPNNDialog]);

  const handleOpenFold2Close = useCallback(() => {
    setShowOpenFold2Dialog(false);
    addMessage({
      id: uuidv4(),
      content: "You've cancelled the structure prediction. What else can I help you with?",
      type: 'ai',
      timestamp: new Date(),
    });
  }, [addMessage, setShowOpenFold2Dialog]);

  return {
    handleAlphaFoldConfirm,
    handleOpenFold2Confirm,
    handleDiffDockConfirm,
    handleDiffDockClose,
    handleProteinMPNNConfirm,
    handleRFdiffusionConfirm,
    handleAlphaFoldClose,
    handleRFdiffusionClose,
    handleProteinMPNNClose,
    handleOpenFold2Close,
  };
}
