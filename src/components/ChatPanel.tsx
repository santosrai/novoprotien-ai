import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Sparkles } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import type { StructureOrigin } from '../stores/appStore';
import { useChatHistoryStore, useActiveSession, Message } from '../stores/chatHistoryStore';
import { CodeExecutor } from '../utils/codeExecutor';
import { api, getAuthHeaders } from '../utils/api';
import { toLangGraphMessages } from '../utils/langgraphTransport';
import { useModels, useAgents } from '../hooks/queries';
import { v4 as uuidv4 } from 'uuid';
import { useAlphaFoldProgress, useProteinMPNNProgress } from './ProgressTracker';
import { useAlphaFoldCancel } from '../hooks/mutations/useAlphaFold';
import { useDiffDockPredict } from '../hooks/mutations/useDiffDock';
import { useAgentSettings, useSettingsStore } from '../stores/settingsStore';
import { usePipelineStore } from '../components/pipeline-canvas';
import { extractStructureMetadata, summarizeForAgent } from '../utils/structureMetadata';

import { AlphaFoldDialog } from './AlphaFoldDialog';
import { OpenFold2Dialog } from './OpenFold2Dialog';
import { DiffDockDialog } from './DiffDockDialog';
import { RFdiffusionDialog } from './RFdiffusionDialog';
import { ProteinMPNNDialog } from './ProteinMPNNDialog';
import { PipelineSelectionModal } from './PipelineSelectionModal';
import { ServerFilesDialog } from './ServerFilesDialog';

import type { ExtendedMessage, FileUploadState } from '../types/chat';

import { useChatSession } from '../hooks/useChatSession';
import { useLangGraphStream } from '../hooks/useLangGraphStream';
import { useViewerLoader } from '../hooks/useViewerLoader';
import { useJobHandlers } from '../hooks/useJobHandlers';
import { useActionRouter } from '../hooks/useActionRouter';

import { MessageList } from './chat/MessageList';
import { WelcomeScreen } from './chat/WelcomeScreen';
import { ChatInput } from './chat/ChatInput';

export const ChatPanel: React.FC = () => {
  const {
    plugin, currentCode, currentStructureOrigin,
    setCurrentCode, setIsExecuting, setActivePane,
    setPendingCodeToRun, setViewerVisible, setCurrentStructureOrigin,
    pendingCodeToRun,
  } = useAppStore();
  const selections = useAppStore(state => state.selections);
  const removeSelection = useAppStore(state => state.removeSelection);
  const clearSelections = useAppStore(state => state.clearSelections);
  const { setGhostBlueprint } = usePipelineStore();

  const {
    createSession, activeSessionId,
    saveVisualizationCode, getVisualizationCode,
    getLastCanvasCodeFromSession, saveViewerVisibility, getViewerVisibility,
  } = useChatHistoryStore();
  const isViewerVisible = useAppStore(state => state.isViewerVisible);
  const { activeSession, addMessage, updateMessages } = useActiveSession();
  const activeSessionMessageCount = activeSession?.messages?.length ?? -1;

  const { settings: agentSettings } = useAgentSettings();
  const langsmithSettings = useSettingsStore((s) => s.settings?.langsmith);

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [, setLastAgentId] = useState<string>('');
  const [isQuickStartExpanded, setIsQuickStartExpanded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [fileUploads, setFileUploads] = useState<FileUploadState[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [showPipelineModal, setShowPipelineModal] = useState(false);
  const [showServerFilesDialog, setShowServerFilesDialog] = useState(false);
  const [selectedPipeline, setSelectedPipeline] = useState<{ id: string; name: string } | null>(null);
  const displayAttachedPipeline = selectedPipeline;

  // Dialog states
  const [showAlphaFoldDialog, setShowAlphaFoldDialog] = useState(false);
  const [alphafoldData, setAlphafoldData] = useState<any>(null);
  const [showProteinMPNNDialog, setShowProteinMPNNDialog] = useState(false);
  const [proteinmpnnData, setProteinmpnnData] = useState<any>(null);
  const [showOpenFold2Dialog, setShowOpenFold2Dialog] = useState(false);
  const [showDiffDockDialog, setShowDiffDockDialog] = useState(false);
  const [showRFdiffusionDialog, setShowRFdiffusionDialog] = useState(false);
  const [rfdiffusionData, setRfdiffusionData] = useState<any>(null);

  // Progress and mutations
  const alphafoldProgress = useAlphaFoldProgress();
  const alphafoldCancelMutation = useAlphaFoldCancel();
  const [isCancellingAlphaFold, setIsCancellingAlphaFold] = useState(false);
  const proteinmpnnProgress = useProteinMPNNProgress();
  const diffdockPredictMutation = useDiffDockPredict();

  const isSyncing = useChatHistoryStore(state => state._isSyncing);
  const sessions = useChatHistoryStore(state => state.sessions);

  useAgents();
  const { data: modelsData } = useModels();
  const models = modelsData ?? [];

  const rawMessages = activeSession?.messages || [];

  // --- Hooks ---

  const { setViewerVisibleAndSave } = useChatSession({
    activeSessionId, activeSession, activeSessionMessageCount,
    currentCode, isViewerVisible, isSyncing, sessions,
    createSession, getVisualizationCode, getLastCanvasCodeFromSession,
    saveVisualizationCode, getViewerVisibility, saveViewerVisibility,
    setCurrentCode, setViewerVisible, setActivePane,
  });

  const { loadUploadedFileInViewer, loadSmilesInViewer } = useViewerLoader({
    plugin, activeSessionId, setIsExecuting, setCurrentCode,
    setCurrentStructureOrigin, setPendingCodeToRun, setViewerVisibleAndSave,
    setActivePane, saveVisualizationCode,
  });

  const { routeAction } = useActionRouter({
    setAlphafoldData, setShowAlphaFoldDialog,
    setRfdiffusionData, setShowRFdiffusionDialog,
    setProteinmpnnData, setShowProteinMPNNDialog,
    setShowOpenFold2Dialog, setShowDiffDockDialog,
    addMessage, loadSmilesInViewer,
  });

  const { stream, messages, hasStreamingContent } = useLangGraphStream({
    rawMessages, activeSessionId, isLoading, setIsLoading,
    addMessage, setLastAgentId, setCurrentCode, saveVisualizationCode,
    setIsExecuting, setPendingCodeToRun, setViewerVisibleAndSave,
    setActivePane, routeAction,
  });

  const jobHandlers = useJobHandlers({
    activeSession, activeSessionId, addMessage, updateMessages,
    alphafoldProgress, proteinmpnnProgress, diffdockPredictMutation,
    setShowAlphaFoldDialog, setShowOpenFold2Dialog, setShowDiffDockDialog,
    setShowRFdiffusionDialog, setShowProteinMPNNDialog,
  });

  // Auto-show viewer when pendingCodeToRun is set
  useEffect(() => {
    if (pendingCodeToRun && pendingCodeToRun.trim()) {
      setViewerVisibleAndSave(true);
      setActivePane('viewer');
    }
  }, [pendingCodeToRun, setViewerVisibleAndSave, setActivePane]);

  // Scroll + textarea resize
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // --- AlphaFold cancel ---
  const handleAlphaFoldCancel = async () => {
    const jobId = alphafoldProgress.currentJobId;
    if (!jobId || isCancellingAlphaFold) return;
    const confirmed = window.confirm('Cancel AlphaFold job? This stops processing on NVIDIA and frees your slot.');
    if (!confirmed) return;
    try {
      setIsCancellingAlphaFold(true);
      await alphafoldCancelMutation.mutateAsync(jobId);
      alphafoldProgress.cancelProgress();
    } catch (err) {
      console.error('[AlphaFold] Cancel failed', err);
      alert('Cancel failed. Please try again.');
    } finally {
      setIsCancellingAlphaFold(false);
    }
  };

  // --- Helpers ---
  const formatSelection = (selection: any) => {
    const chain = selection.labelAsymId ?? selection.authAsymId ?? '';
    const seq = selection.labelSeqId != null && selection.labelSeqId !== ''
      ? selection.labelSeqId
      : selection.authSeqId != null ? selection.authSeqId : '';
    const chainText = chain ? ` (${chain})` : '';
    return `${selection.compId || '?'}${seq !== '' ? seq : ''}${chainText}`;
  };

  const isValidUploadedFile = (
    fileInfo: Message['uploadedFile']
  ): fileInfo is NonNullable<Message['uploadedFile']> => {
    return !!(fileInfo && fileInfo.file_id && fileInfo.filename && fileInfo.file_url
      && typeof fileInfo.atoms === 'number' && Array.isArray(fileInfo.chains));
  };

  const handleValidateStructure = async (pdbContent: string) => {
    try {
      const { validateStructure } = await import('../utils/api');
      addMessage({ id: uuidv4(), content: 'Running structure validation...', type: 'ai', timestamp: new Date() });
      const report = await validateStructure(pdbContent);
      addMessage({
        id: uuidv4(),
        content: `Structure validation complete - Grade: ${report.grade}`,
        type: 'ai', timestamp: new Date(), validationResult: report,
      } as ExtendedMessage);
    } catch (error) {
      addMessage({
        id: uuidv4(),
        content: `Validation failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        type: 'ai', timestamp: new Date(),
      });
    }
  };

  // --- File upload ---
  const uploadFile = async (file: File) => {
    setFileUploads(prev => prev.map(item =>
      item.file === file ? { ...item, status: 'uploading' } : item
    ));
    try {
      setUploadError(null);
      const formData = new FormData();
      formData.append('file', file);
      if (activeSessionId) formData.append('session_id', activeSessionId);

      const headers = getAuthHeaders();
      const response = await fetch('/api/upload/pdb', { method: 'POST', headers, body: formData });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const result = await response.json();
      const fileInfo = {
        file_id: result.file_info.file_id,
        filename: result.file_info.filename,
        file_url: result.file_info.file_url,
        atoms: result.file_info.atoms,
        chains: result.file_info.chains,
        size: result.file_info.size || 0,
        chain_residue_counts: result.file_info.chain_residue_counts,
        total_residues: result.file_info.total_residues,
      };

      let isFirstFile = false;
      setFileUploads(prev => {
        const updated = prev.map(item =>
          item.file === file ? { ...item, status: 'uploaded' as const, fileInfo } : item
        );
        isFirstFile = updated.findIndex(item => item.status === 'uploaded') === 0;
        return updated;
      });

      window.dispatchEvent(new CustomEvent('session-file-added'));
      setCurrentCode('');
      setCurrentStructureOrigin(null);

      if (isFirstFile && plugin) {
        try {
          setIsExecuting(true);
          const executor = new CodeExecutor(plugin);
          await executor.executeCode('try { await builder.clearStructure(); } catch(e) { console.warn("Clear failed:", e); }');
          const fileUrl = result.file_info.file_url || `/api/upload/pdb/${result.file_info.file_id}`;
          const fileResponse = await fetch(fileUrl, { headers: getAuthHeaders() });
          if (!fileResponse.ok) throw new Error('Failed to fetch uploaded file');
          const fileContent = await fileResponse.text();
          const pdbBlob = new Blob([fileContent], { type: 'text/plain' });
          const blobUrl = URL.createObjectURL(pdbBlob);
          const loadCode = `\ntry {\n  await builder.loadStructure('${blobUrl}');\n  await builder.addCartoonRepresentation({ color: 'secondary-structure' });\n  builder.focusView();\n  console.log('Uploaded file loaded successfully');\n} catch (e) { \n  console.error('Failed to load uploaded file:', e); \n}`;
          setCurrentCode(loadCode);
          setCurrentStructureOrigin({ type: 'upload', filename: result.file_info.filename, metadata: { file_id: result.file_info.file_id, file_url: blobUrl } });
          if (activeSessionId) saveVisualizationCode(activeSessionId, loadCode);
          await executor.executeCode(loadCode);
          setViewerVisibleAndSave(true);
          setActivePane('viewer');
          setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);
        } catch (viewerError) {
          console.error('Failed to auto-load uploaded file in viewer:', viewerError);
        } finally {
          setIsExecuting(false);
        }
      }
    } catch (error: any) {
      console.error('File upload failed:', error);
      setUploadError(error.message);
      setFileUploads(prev => prev.map(item =>
        item.file === file ? { ...item, status: 'error', error: error.message } : item
      ));
    }
  };

  const handleFileSelected = (file: File) => {
    setFileUploads(prev => [...prev, { file, status: 'uploading' }]);
    uploadFile(file);
  };
  const handleFilesSelected = (files: File[]) => {
    setFileUploads(prev => [...prev, ...files.map(file => ({ file, status: 'uploading' as const }))]);
    files.forEach(file => uploadFile(file));
  };
  const handlePipelineSelect = () => setShowPipelineModal(true);
  const handleServerFilesSelect = () => setShowServerFilesDialog(true);
  const handlePipelineSelected = (pipelineId: string) => {
    const { savedPipelines } = usePipelineStore.getState();
    const pipeline = savedPipelines.find(p => p.id === pipelineId);
    if (pipeline) setSelectedPipeline({ id: pipeline.id, name: pipeline.name });
    setShowPipelineModal(false);
  };

  // --- Submit ---
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const uploadedFileInfo = fileUploads.find(f => f.status === 'uploaded' && f.fileInfo)?.fileInfo || null;
    const attachedPipeline = selectedPipeline;

    const userMessage: Message = {
      id: uuidv4(),
      content: input.trim(),
      type: 'user',
      timestamp: new Date(),
      uploadedFile: uploadedFileInfo || undefined,
      pipeline: attachedPipeline ? {
        id: attachedPipeline.id, name: attachedPipeline.name,
        workflowDefinition: null, status: 'draft' as const,
      } : undefined,
    };

    addMessage(userMessage);
    const messageInput = input.trim();
    setInput('');
    setIsLoading(true);
    setFileUploads([]);
    const pipelineIdToSend = attachedPipeline?.id ?? undefined;
    setSelectedPipeline(null);

    try {
      let structureMetadata: Awaited<ReturnType<typeof extractStructureMetadata>> = null;
      if (plugin) {
        try {
          const raw = await extractStructureMetadata(plugin);
          structureMetadata = raw ? summarizeForAgent(raw) : null;
        } catch (e) {
          console.warn('[ChatPanel] Failed to extract structure metadata:', e);
        }
      }

      const payload = {
        input: messageInput,
        currentCode,
        history: messages.slice(-6).map(m => ({ type: m.type, content: m.content })),
        selection: selections.length > 0 ? selections[0] : null,
        selections,
        currentStructureOrigin: currentStructureOrigin || undefined,
        uploadedFile: uploadedFileInfo
          ? { file_id: uploadedFileInfo.file_id, filename: uploadedFileInfo.filename, file_url: uploadedFileInfo.file_url, atoms: uploadedFileInfo.atoms, chains: uploadedFileInfo.chains, chain_residue_counts: uploadedFileInfo.chain_residue_counts, total_residues: uploadedFileInfo.total_residues }
          : undefined,
        structureMetadata: structureMetadata || undefined,
        agentId: agentSettings.selectedAgentId || undefined,
        model: agentSettings.selectedModel || undefined,
        pipeline_id: pipelineIdToSend,
        pdb_content: undefined as string | undefined,
        langsmith: langsmithSettings?.enabled
          ? { enabled: true, apiKey: langsmithSettings.apiKey || undefined, project: langsmithSettings.project || undefined }
          : { enabled: false },
      };

      const sessionMessages = activeSession?.messages ?? [];
      const lcMessages = [...toLangGraphMessages(sessionMessages), { type: 'human' as const, content: messageInput }];
      const configurable = {
        currentCode,
        history: payload.history,
        selection: payload.selection,
        selections: payload.selections,
        uploadedFile: payload.uploadedFile,
        structureMetadata: payload.structureMetadata,
        pipeline_id: payload.pipeline_id,
        model: payload.model,
        agentId: payload.agentId,
      };

      try {
        await stream.submit({ messages: lcMessages }, { config: { configurable } });
      } catch (submitErr) {
        addMessage({
          id: uuidv4(), type: 'ai',
          content: `Stream error: ${submitErr instanceof Error ? submitErr.message : String(submitErr)}`,
          timestamp: new Date(),
        } as ExtendedMessage);
        setIsLoading(false);
      }
    } catch (err) {
      console.error('[Molstar] chat flow failed', err);
      addMessage({ id: uuidv4(), content: 'Sorry, I could not visualize that just now.', type: 'ai', timestamp: new Date() });
      setIsLoading(false);
    }
  };

  // --- Layout ---
  const quickPrompts = ['Show insulin', 'Display hemoglobin', 'Visualize DNA double helix', 'Show antibody structure'];
  const hasUserMessages = messages.some(m => m.type === 'user');
  const isOnlyWelcomeMessage = messages.length === 1 && messages[0].type === 'ai' && messages[0].content.includes('Welcome to NovoProtein AI');
  const showCenteredLayout = !isLoading && !hasUserMessages && (messages.length === 0 || isOnlyWelcomeMessage);

  // Viewer loading callbacks for result cards
  const onLoadAlphaFoldInViewer = useCallback(async (result: any, message?: any) => {
    if (!result.pdbContent || !plugin) return;
    try {
      setIsExecuting(true);
      const executor = new CodeExecutor(plugin);
      const storeRes = await api.post('/upload/pdb/from-content', { pdbContent: result.pdbContent, filename: result.filename || 'alphafold_result.pdb' });
      const fileId = storeRes.data?.file_info?.file_id;
      const apiUrl = fileId ? `/api/upload/pdb/${fileId}` : null;
      if (!apiUrl) throw new Error('Failed to store PDB');
      const blobRes = await api.get(`/upload/pdb/${fileId}`, { responseType: 'blob' });
      const blob = new Blob([blobRes.data], { type: 'chemical/x-pdb' });
      const blobUrl = URL.createObjectURL(blob);
      const execCode = `\ntry {\n  await builder.clearStructure();\n  await builder.loadStructure('${blobUrl}');\n  await builder.addCartoonRepresentation({ color: 'secondary-structure' });\n  builder.focusView();\n} catch (e) { \n  console.error('Failed to load AlphaFold result:', e); \n}`;
      const savedCode = `\ntry {\n  await builder.clearStructure();\n  await builder.loadStructure('${apiUrl}');\n  await builder.addCartoonRepresentation({ color: 'secondary-structure' });\n  builder.focusView();\n} catch (e) { \n  console.error('Failed to load AlphaFold result:', e); \n}`;
      await executor.executeCode(execCode);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);
      setCurrentCode(savedCode);
      if (activeSessionId) saveVisualizationCode(activeSessionId, savedCode, message?.id);
      setViewerVisibleAndSave(true);
      setActivePane('viewer');
      setCurrentStructureOrigin({ type: 'alphafold', filename: result.filename || 'alphafold_result.pdb' });
    } catch (err) { console.error('Failed to load AlphaFold result in viewer:', err); }
    finally { setIsExecuting(false); }
  }, [plugin, activeSessionId, saveVisualizationCode, setIsExecuting, setCurrentCode, setViewerVisibleAndSave, setActivePane, setCurrentStructureOrigin]);

  const makeViewerCallback = useCallback((type: string, defaultFilename: string, colorScheme = 'bfactor') => {
    return async (result: any, message?: any) => {
      if (!plugin) return;
      const pdbContent = result.pdbContent;
      const resultUrl = result.pdb_url ?? (result.job_id ? `/api/${type}/result/${result.job_id}` : null);
      try {
        setIsExecuting(true);
        const executor = new CodeExecutor(plugin);
        let apiUrl: string;
        let blobRes: { data: BlobPart };
        if (resultUrl) {
          apiUrl = resultUrl;
          blobRes = await api.get(apiUrl.replace(/^\/api/, ''), { responseType: 'blob' });
        } else if (pdbContent) {
          const storeRes = await api.post('/upload/pdb/from-content', { pdbContent, filename: result.filename || defaultFilename });
          const fileId = storeRes.data?.file_info?.file_id;
          apiUrl = fileId ? `/api/upload/pdb/${fileId}` : '';
          if (!apiUrl) throw new Error('Failed to store PDB');
          blobRes = await api.get(`/upload/pdb/${fileId}`, { responseType: 'blob' });
        } else return;
        const blob = new Blob([blobRes.data], { type: 'chemical/x-pdb' });
        const blobUrl = URL.createObjectURL(blob);
        const execCode = `\ntry {\n  await builder.clearStructure();\n  await builder.loadStructure('${blobUrl}');\n  await builder.addCartoonRepresentation({ color: '${colorScheme}' });\n  builder.focusView();\n} catch (e) { console.error('Failed to load ${type} result:', e); }`;
        const savedCode = `\ntry {\n  await builder.clearStructure();\n  await builder.loadStructure('${apiUrl}');\n  await builder.addCartoonRepresentation({ color: '${colorScheme}' });\n  builder.focusView();\n} catch (e) { console.error('Failed to load ${type} result:', e); }`;
        await executor.executeCode(execCode);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);
        setCurrentCode(savedCode);
        if (activeSessionId) saveVisualizationCode(activeSessionId, savedCode, message?.id);
        setViewerVisibleAndSave(true);
        setActivePane('viewer');
        setCurrentStructureOrigin({ type: type as StructureOrigin['type'], filename: result.filename || defaultFilename });
      } catch (err) { console.error(`Failed to load ${type} result in viewer:`, err); }
      finally { setIsExecuting(false); }
    };
  }, [plugin, activeSessionId, saveVisualizationCode, setIsExecuting, setCurrentCode, setViewerVisibleAndSave, setActivePane, setCurrentStructureOrigin]);

  const onLoadOpenFold2InViewer = useCallback(makeViewerCallback('openfold2', 'openfold2_result.pdb', 'bfactor'), [makeViewerCallback]);
  const onLoadDiffDockInViewer = useCallback(makeViewerCallback('diffdock', 'diffdock_result.pdb', 'bfactor'), [makeViewerCallback]);
  const onLoadRFdiffusionInViewer = useCallback(makeViewerCallback('rfdiffusion', 'rfdiffusion_design.pdb', 'secondary-structure'), [makeViewerCallback]);

  const onLoadSmilesInViewer = useCallback(async (result: any, message?: any) => {
    if (!result?.file_id || !plugin) return;
    try {
      setIsExecuting(true);
      const executor = new CodeExecutor(plugin);
      const blobRes = await api.get(`/upload/pdb/${result.file_id}`, { responseType: 'blob' });
      const blob = new Blob([blobRes.data], { type: 'chemical/x-pdb' });
      const blobUrl = URL.createObjectURL(blob);
      const apiUrl = result.file_url;
      const execCode = `\ntry {\n  await builder.clearStructure();\n  await builder.loadStructure('${blobUrl}');\n  await builder.addBallAndStickRepresentation({ color: 'element' });\n  builder.focusView();\n} catch (e) { console.error('Failed to load SMILES structure:', e); }`;
      const savedCode = `\ntry {\n  await builder.clearStructure();\n  await builder.loadStructure('${apiUrl}');\n  await builder.addBallAndStickRepresentation({ color: 'element' });\n  builder.focusView();\n} catch (e) { console.error('Failed to load SMILES structure:', e); }`;
      await executor.executeCode(execCode);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);
      setCurrentCode(savedCode);
      if (activeSessionId) saveVisualizationCode(activeSessionId, savedCode, message?.id);
      setViewerVisibleAndSave(true);
      setActivePane('viewer');
      setCurrentStructureOrigin({ type: 'upload', filename: result.filename, metadata: { file_id: result.file_id, file_url: result.file_url } });
    } catch (err) { console.error('[ChatPanel] Failed to load SMILES result in viewer:', err); }
    finally { setIsExecuting(false); }
  }, [plugin, activeSessionId, saveVisualizationCode, setIsExecuting, setCurrentCode, setViewerVisibleAndSave, setActivePane, setCurrentStructureOrigin]);

  const onDownloadSmiles = useCallback(async (result: any) => {
    try {
      const res = await api.get(`/upload/pdb/${result.file_id}`, { responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'chemical/x-pdb' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = result.filename || 'smiles_structure.pdb';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) { console.error('[ChatPanel] Failed to download SMILES PDB:', e); }
  }, []);

  return (
    <div className="h-full flex flex-col">
      {!showCenteredLayout && (
        <div className="px-3 py-1.5 border-b border-gray-200 flex-shrink-0">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
            <div>
              <h2 className="text-xs font-semibold text-gray-900">AI Assistant</h2>
              {activeSession && (
                <p className="text-[10px] text-gray-500 truncate max-w-[180px]">{activeSession.title}</p>
              )}
            </div>
          </div>
        </div>
      )}

      {!showCenteredLayout ? (
        <MessageList
          messages={messages as ExtendedMessage[]}
          isLoading={isLoading}
          hasStreamingContent={hasStreamingContent}
          messagesEndRef={messagesEndRef as React.RefObject<HTMLDivElement>}
          plugin={plugin}
          activeSession={activeSession}
          updateMessages={updateMessages}
          setCurrentCode={setCurrentCode}
          setPendingCodeToRun={setPendingCodeToRun}
          onLoadAlphaFoldInViewer={onLoadAlphaFoldInViewer}
          onLoadSmilesInViewer={onLoadSmilesInViewer}
          onDownloadSmiles={onDownloadSmiles}
          onLoadOpenFold2InViewer={onLoadOpenFold2InViewer}
          onLoadDiffDockInViewer={onLoadDiffDockInViewer}
          onLoadRFdiffusionInViewer={onLoadRFdiffusionInViewer}
          onLoadFileInViewer={loadUploadedFileInViewer}
          onValidateStructure={handleValidateStructure}
          onRetryAlphaFold={jobHandlers.handleAlphaFoldConfirm}
          setGhostBlueprint={setGhostBlueprint}
          isValidUploadedFile={isValidUploadedFile}
        />
      ) : (
        <WelcomeScreen isLoading={isLoading} />
      )}

      <ChatInput
        input={input}
        setInput={setInput}
        isLoading={isLoading}
        showCenteredLayout={showCenteredLayout}
        selections={selections}
        removeSelection={removeSelection}
        clearSelections={clearSelections}
        formatSelection={formatSelection}
        fileUploads={fileUploads}
        setFileUploads={setFileUploads}
        uploadError={uploadError}
        setUploadError={setUploadError}
        displayAttachedPipeline={displayAttachedPipeline}
        setSelectedPipeline={setSelectedPipeline}
        alphafoldProgress={alphafoldProgress}
        proteinmpnnProgress={proteinmpnnProgress}
        handleAlphaFoldCancel={handleAlphaFoldCancel}
        isCancellingAlphaFold={isCancellingAlphaFold}
        isQuickStartExpanded={isQuickStartExpanded}
        setIsQuickStartExpanded={setIsQuickStartExpanded}
        quickPrompts={quickPrompts}
        models={models}
        textareaRef={textareaRef as React.RefObject<HTMLTextAreaElement>}
        handleSubmit={handleSubmit}
        handleFileSelected={handleFileSelected}
        handleFilesSelected={handleFilesSelected}
        handlePipelineSelect={handlePipelineSelect}
        handleServerFilesSelect={handleServerFilesSelect}
        activeSessionId={activeSessionId}
        setShowOpenFold2Dialog={setShowOpenFold2Dialog}
        setShowDiffDockDialog={setShowDiffDockDialog}
      />

      <AlphaFoldDialog isOpen={showAlphaFoldDialog} onClose={jobHandlers.handleAlphaFoldClose} onConfirm={jobHandlers.handleAlphaFoldConfirm} initialData={alphafoldData} />
      <RFdiffusionDialog isOpen={showRFdiffusionDialog} onClose={jobHandlers.handleRFdiffusionClose} onConfirm={jobHandlers.handleRFdiffusionConfirm} initialData={rfdiffusionData} />
      <ProteinMPNNDialog isOpen={showProteinMPNNDialog} onClose={jobHandlers.handleProteinMPNNClose} onConfirm={jobHandlers.handleProteinMPNNConfirm} initialData={proteinmpnnData} />
      <OpenFold2Dialog isOpen={showOpenFold2Dialog} onClose={jobHandlers.handleOpenFold2Close} onConfirm={jobHandlers.handleOpenFold2Confirm} />
      <DiffDockDialog isOpen={showDiffDockDialog} onClose={jobHandlers.handleDiffDockClose} onConfirm={jobHandlers.handleDiffDockConfirm} />
      <PipelineSelectionModal isOpen={showPipelineModal} onClose={() => setShowPipelineModal(false)} onPipelineSelect={handlePipelineSelected} />
      <ServerFilesDialog
        isOpen={showServerFilesDialog}
        onClose={() => setShowServerFilesDialog(false)}
        onFileSelect={(file) => { handleFileSelected(file); setShowServerFilesDialog(false); }}
        onError={(error) => setUploadError(error)}
      />
    </div>
  );
};
