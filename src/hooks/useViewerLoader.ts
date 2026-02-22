import { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';
import { useAppStore } from '../stores/appStore';
import { api } from '../utils/api';

export interface UseViewerLoaderParams {
  plugin: any;
  activeSessionId: string | null;
  setIsExecuting: (v: boolean) => void;
  setCurrentCode: (code: string) => void;
  setCurrentStructureOrigin: (origin: any) => void;
  setPendingCodeToRun: (code: string) => void;
  setViewerVisibleAndSave: (visible: boolean) => void;
  setActivePane: (pane: 'viewer' | 'editor' | 'files' | 'pipeline' | null) => void;
  saveVisualizationCode: (sessionId: string, code: string, messageId?: string) => void;
}

export function useViewerLoader(params: UseViewerLoaderParams) {
  const {
    activeSessionId,
    setIsExecuting,
    setCurrentCode,
    setCurrentStructureOrigin,
    setPendingCodeToRun,
    setViewerVisibleAndSave,
    setActivePane,
    saveVisualizationCode,
  } = params;

  const waitForPlugin = async (
    maxWait = 15000,
    retryInterval = 200
  ): Promise<PluginUIContext | null> => {
    const startTime = Date.now();
    while (Date.now() - startTime < maxWait) {
      const currentPlugin = useAppStore.getState().plugin;
      if (currentPlugin) {
        try {
          if (currentPlugin.builders && currentPlugin.builders.data && currentPlugin.builders.structure) {
            return currentPlugin;
          }
        } catch (e) {
          //
        }
      }
      await new Promise(resolve => setTimeout(resolve, retryInterval));
    }
    return null;
  };

  const loadUploadedFileInViewer = async (fileInfo: {
    file_id: string;
    filename: string;
    file_url: string;
  }) => {
    const apiUrl = `/api/upload/pdb/${fileInfo.file_id}`;

    const code = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${apiUrl}');
  await builder.addCartoonRepresentation({ color: 'secondary-structure' });
  builder.focusView();
  console.log('Uploaded file loaded successfully');
} catch (e) { 
  console.error('Failed to load uploaded file:', e); 
}`;

    setCurrentStructureOrigin({
      type: 'upload',
      filename: fileInfo.filename,
      metadata: {
        file_id: fileInfo.file_id,
        file_url: fileInfo.file_url,
      },
    });

    setCurrentCode('');
    setViewerVisibleAndSave(true);
    setActivePane('viewer');

    const readyPlugin = await waitForPlugin();

    if (!readyPlugin) {
      console.warn('[ChatPanel] Plugin not ready after timeout, queuing code for execution');
      setCurrentCode(code);
      setPendingCodeToRun(code);
      return;
    }

    try {
      setIsExecuting(true);
      const { createMolstarBuilder } = await import('../utils/molstarBuilder');
      const builder = createMolstarBuilder(readyPlugin);
      await builder.clearStructure();
      await builder.loadStructure(apiUrl);
      await builder.addCartoonRepresentation({ color: 'secondary-structure' });
      builder.focusView();
      console.log('[ChatPanel] Uploaded file loaded successfully in 3D viewer');

      setCurrentCode(code);
      if (activeSessionId) {
        saveVisualizationCode(activeSessionId, code);
        console.log('[ChatPanel] Saved visualization code to session:', activeSessionId);
      }
    } catch (err) {
      console.error('[ChatPanel] Failed to load uploaded file in viewer:', err);
      alert(`Failed to load ${fileInfo.filename} in 3D viewer. Please try again.`);
    } finally {
      setIsExecuting(false);
    }
  };

  const loadSmilesInViewer = async (smilesData: {
    smiles: string;
    format?: string;
  }): Promise<{ file_id: string; file_url: string; filename: string }> => {
    let response: { content: string; filename: string; format: string };
    try {
      const res = await api.post<{ content: string; filename: string; format: string }>(
        '/smiles/to-structure',
        { smiles: smilesData.smiles.trim(), format: 'pdb' }
      );
      response = res.data;
    } catch (err: any) {
      const userMessage =
        err?.response?.data?.userMessage ||
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to convert SMILES to structure.';
      throw new Error(userMessage);
    }

    let fileId: string;
    let apiUrl: string;
    try {
      const storeRes = await api.post<{ file_info: { file_id: string; filename: string } }>(
        '/upload/pdb/from-content',
        { pdbContent: response.content, filename: response.filename || 'smiles_structure.pdb' }
      );
      fileId = storeRes.data?.file_info?.file_id;
      apiUrl = fileId ? `/api/upload/pdb/${fileId}` : '';
      if (!fileId || !apiUrl) throw new Error('Failed to store SMILES PDB');
      window.dispatchEvent(new CustomEvent('session-file-added'));
    } catch (err: any) {
      console.error('[ChatPanel] Failed to store SMILES PDB:', err);
      throw new Error(err?.response?.data?.detail || err?.message || 'Failed to store structure.');
    }

    setViewerVisibleAndSave(true);
    setActivePane('viewer');

    const filename = response.filename || 'smiles_structure.pdb';
    const fileInfo = { file_id: fileId, file_url: apiUrl, filename };

    const readyPlugin = await waitForPlugin();
    if (!readyPlugin) {
      setCurrentCode(`// SMILES structure stored as ${filename}; load when viewer is ready:\ntry {\n  await builder.clearStructure();\n  await builder.loadStructure('${apiUrl}');\n  await builder.addBallAndStickRepresentation({ color: 'element' });\n  builder.focusView();\n} catch (e) { console.error(e); }`);
      setCurrentStructureOrigin({
        type: 'upload',
        filename,
        metadata: { file_id: fileId, file_url: apiUrl },
      });
      setPendingCodeToRun('// SMILES structure will load when viewer is ready');
      return fileInfo;
    }

    try {
      setIsExecuting(true);
      const { CodeExecutor } = await import('../utils/codeExecutor');
      const executor = new CodeExecutor(readyPlugin);
      const blobRes = await api.get(`/upload/pdb/${fileId}`, { responseType: 'blob' });
      const blob = new Blob([blobRes.data], { type: 'chemical/x-pdb' });
      const blobUrl = URL.createObjectURL(blob);
      const execCode = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${blobUrl}');
  await builder.addBallAndStickRepresentation({ color: 'element' });
  builder.focusView();
} catch (e) { 
  console.error('Failed to load SMILES structure:', e); 
}`;
      const savedCode = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${apiUrl}');
  await builder.addBallAndStickRepresentation({ color: 'element' });
  builder.focusView();
} catch (e) { 
  console.error('Failed to load SMILES structure:', e); 
}`;
      await executor.executeCode(execCode);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);
      setCurrentCode(savedCode);
      if (activeSessionId) saveVisualizationCode(activeSessionId, savedCode);
      setCurrentStructureOrigin({
        type: 'upload',
        filename,
        metadata: { file_id: fileId, file_url: apiUrl },
      });
      return fileInfo;
    } catch (err) {
      console.error('[ChatPanel] Failed to load SMILES in viewer:', err);
      throw err;
    } finally {
      setIsExecuting(false);
    }
  };

  const loadSmilesResultInViewer = async (payload: {
    content: string;
    filename: string;
  }): Promise<{ file_id: string; file_url: string; filename: string }> => {
    const { content, filename } = payload;
    let fileId: string;
    let apiUrl: string;
    try {
      const storeRes = await api.post<{ file_info: { file_id: string; filename: string } }>(
        '/upload/pdb/from-content',
        { pdbContent: content, filename: filename || 'smiles_structure.pdb' }
      );
      fileId = storeRes.data?.file_info?.file_id;
      apiUrl = fileId ? `/api/upload/pdb/${fileId}` : '';
      if (!fileId || !apiUrl) throw new Error('Failed to store SMILES PDB');
      window.dispatchEvent(new CustomEvent('session-file-added'));
    } catch (err: any) {
      console.error('[ChatPanel] Failed to store SMILES PDB:', err);
      throw new Error(err?.response?.data?.detail || err?.message || 'Failed to store structure.');
    }

    setViewerVisibleAndSave(true);
    setActivePane('viewer');

    const fileInfo = { file_id: fileId, file_url: apiUrl, filename: filename || 'smiles_structure.pdb' };
    const readyPlugin = await waitForPlugin();
    if (!readyPlugin) {
      setCurrentCode(`// SMILES structure stored as ${fileInfo.filename}; load when viewer is ready:\ntry {\n  await builder.clearStructure();\n  await builder.loadStructure('${apiUrl}');\n  await builder.addBallAndStickRepresentation({ color: 'element' });\n  builder.focusView();\n} catch (e) { console.error(e); }`);
      setCurrentStructureOrigin({
        type: 'upload',
        filename: fileInfo.filename,
        metadata: { file_id: fileId, file_url: apiUrl },
      });
      setPendingCodeToRun('// SMILES structure will load when viewer is ready');
      return fileInfo;
    }

    try {
      setIsExecuting(true);
      const { CodeExecutor } = await import('../utils/codeExecutor');
      const executor = new CodeExecutor(readyPlugin);
      const blobRes = await api.get(`/upload/pdb/${fileId}`, { responseType: 'blob' });
      const blob = new Blob([blobRes.data], { type: 'chemical/x-pdb' });
      const blobUrl = URL.createObjectURL(blob);
      const execCode = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${blobUrl}');
  await builder.addBallAndStickRepresentation({ color: 'element' });
  builder.focusView();
} catch (e) { 
  console.error('Failed to load SMILES structure:', e); 
}`;
      const savedCode = `
try {
  await builder.clearStructure();
  await builder.loadStructure('${apiUrl}');
  await builder.addBallAndStickRepresentation({ color: 'element' });
  builder.focusView();
} catch (e) { 
  console.error('Failed to load SMILES structure:', e); 
}`;
      await executor.executeCode(execCode);
      setTimeout(() => URL.revokeObjectURL(blobUrl), 5000);
      setCurrentCode(savedCode);
      if (activeSessionId) saveVisualizationCode(activeSessionId, savedCode);
      setCurrentStructureOrigin({
        type: 'upload',
        filename: fileInfo.filename,
        metadata: { file_id: fileId, file_url: apiUrl },
      });
      return fileInfo;
    } catch (err) {
      console.error('[ChatPanel] Failed to load SMILES result in viewer:', err);
      throw err;
    } finally {
      setIsExecuting(false);
    }
  };

  return {
    loadUploadedFileInViewer,
    loadSmilesInViewer,
    loadSmilesResultInViewer,
    waitForPlugin,
  };
}
