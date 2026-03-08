import React, { useEffect, useRef, useState } from 'react';
import 'molstar/build/viewer/molstar.css';
import { createPluginUI } from 'molstar/lib/mol-plugin-ui';
import { DefaultPluginUISpec } from 'molstar/lib/mol-plugin-ui/spec';
import { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';
import { renderReact18 } from 'molstar/lib/mol-plugin-ui/react18';
import { PluginSpec } from 'molstar/lib/mol-plugin/spec';
import { MolViewSpec } from 'molstar/lib/extensions/mvs/behavior';
import { useAppStore } from '../stores/appStore';
import { useChatHistoryStore } from '../stores/chatHistoryStore';
import { StructureElement, StructureProperties } from 'molstar/lib/mol-model/structure';
// OrderedSet no longer needed after switching to getFirstLocation
import { CodeExecutor } from '../utils/codeExecutor';
import { MolstarToolbar } from './MolstarToolbar';
import { ConfidenceScorePanel } from './ConfidenceScorePanel';
import { MolstarSkeleton } from './MolstarSkeleton';
import { getCodeToExecute } from '../utils/codeUtils';

export const MolstarViewer: React.FC = () => {
  const MIN_SKELETON_MS = 300;
  const SKELETON_FADE_MS = 200;
  const isDev = typeof window !== 'undefined' && (
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1'
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const lastExecutedCodeRef = useRef<string>('');
  const pluginRef = useRef<PluginUIContext | null>(null);
  const initAttemptRef = useRef(0);
  const initInProgressRef = useRef(false);
  const mountedRef = useRef(true);
  const loadingStartedAtRef = useRef<number | null>(null);
  const loadingStateRef = useRef<'idle' | 'loading' | 'ending'>('idle');
  const [plugin, setPlugin] = useState<PluginUIContext | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingExiting, setIsLoadingExiting] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [initFailed, setInitFailed] = useState(false);
  const [debugInit, setDebugInit] = useState<{ attempt: number; phase: string; at: string }>({
    attempt: 0,
    phase: 'idle',
    at: '',
  });
  const [pdbLoadError, setPdbLoadError] = useState<{ message: string; pdbId?: string } | null>(null);
  const { setPlugin: setStorePlugin, pendingCodeToRun, setPendingCodeToRun, setActivePane, setIsExecuting, currentCode, setCurrentCode, currentStructureOrigin } = useAppStore();
  const addSelection = useAppStore(state => state.addSelection);
  const lastLoadedPdb = useAppStore(state => state.lastLoadedPdb);
  const { activeSessionId, getActiveSession } = useChatHistoryStore();

  // Helper function to check if code contains blob URLs (expired and should be ignored)
  const hasBlobUrl = (code: string): boolean => {
    return code.includes('blob:http://') || code.includes('blob:https://');
  };

  const PDB_NOT_FOUND_MARKER = 'not found in the RCSB database';
  const setErrorIfPdbNotFound = (error: unknown): void => {
    const message = error instanceof Error ? error.message : String(error);
    if (!message.includes(PDB_NOT_FOUND_MARKER)) return;
    const pdbIdMatch = message.match(/PDB ID "([^"]+)"/);
    setPdbLoadError({ message, pdbId: pdbIdMatch?.[1] });
  };
  const clearErrorOnSuccess = (result: { success?: boolean; error?: string }): void => {
    if (result?.success) setPdbLoadError(null);
    else if (result?.error?.includes(PDB_NOT_FOUND_MARKER)) {
      const pdbIdMatch = result.error.match(/PDB ID "([^"]+)"/);
      setPdbLoadError({ message: result.error, pdbId: pdbIdMatch?.[1] });
    }
  };

  // Get code to execute using shared utility
  const getCode = (): string | null => {
    return getCodeToExecute(currentCode, pendingCodeToRun, activeSessionId, getActiveSession);
  };

  const markInitPhase = (phase: string): void => {
    if (!isDev || !mountedRef.current) return;
    setDebugInit({
      attempt: initAttemptRef.current,
      phase,
      at: new Date().toLocaleTimeString(),
    });
  };

  const beginLoading = (): void => {
    if (loadingStateRef.current === 'loading') return;
    loadingStateRef.current = 'loading';
    loadingStartedAtRef.current = Date.now();
    setIsLoadingExiting(false);
    setIsLoading(true);
  };

  const endLoading = async (): Promise<void> => {
    if (loadingStateRef.current !== 'loading') return;
    loadingStateRef.current = 'ending';

    const startedAt = loadingStartedAtRef.current ?? Date.now();
    const elapsed = Date.now() - startedAt;
    const remaining = Math.max(0, MIN_SKELETON_MS - elapsed);
    if (remaining > 0) {
      await new Promise((resolve) => setTimeout(resolve, remaining));
    }

    if (!mountedRef.current) return;
    setIsLoadingExiting(true);
    await new Promise((resolve) => setTimeout(resolve, SKELETON_FADE_MS));

    if (!mountedRef.current) return;
    setIsLoading(false);
    setIsLoadingExiting(false);
    loadingStartedAtRef.current = null;
    loadingStateRef.current = 'idle';
  };

  // Cleanup blob URLs from currentCode when session changes
  useEffect(() => {
    // Only clear if there's actually blob URL code
    if (currentCode && currentCode.trim() && hasBlobUrl(currentCode)) {
      console.warn('[Molstar] Cleaning up blob URL from currentCode on session change');
      setCurrentCode('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]); // Run when session changes (intentionally not including currentCode to avoid loops)

  useEffect(() => {
    // In React Strict Mode (dev), effect cleanup runs before setup reruns.
    // Reset this flag on each setup so loading completion isn't blocked.
    mountedRef.current = true;

    const initViewer = async () => {
      if (!containerRef.current || isInitialized || initInProgressRef.current) return;

      try {
        initAttemptRef.current += 1;
        initInProgressRef.current = true;
        setInitFailed(false);
        markInitPhase('start');
        beginLoading();
        console.log('[Molstar] initViewer: start');
        console.log('[Molstar] initViewer: containerRef set?', !!containerRef.current);

        // Add timeout to prevent infinite loading
        const initTimeout = setTimeout(() => {
          console.warn('[Molstar] Initialization taking longer than expected...');
        }, 10000); // 10 second warning

        // Clear container before createPluginUI to avoid createRoot-on-used-container warning
        // (occurs when MolstarViewer remounts e.g. in React Strict Mode or on session switch)
        if (containerRef.current.firstChild) {
          containerRef.current.replaceChildren();
        }

        const spec = DefaultPluginUISpec();
        const pluginInstance = await createPluginUI({
          target: containerRef.current,
          render: renderReact18,
          spec: {
            ...spec,
            layout: {
              initial: {
                isExpanded: true,
                showControls: true,
                controlsDisplay: 'reactive',
                regionState: {
                  top: 'full',      // Sequence panel
                  left: 'hidden',
                  right: 'hidden', 
                  bottom: 'hidden',
                }
              }
            },
            behaviors: [
              ...spec.behaviors,
              PluginSpec.Behavior(MolViewSpec)
            ]
          },
        });

        // StrictMode/dev can unmount before async init resolves.
        // Dispose stale instances so they don't conflict with the next mount.
        if (!mountedRef.current) {
          try {
            pluginInstance.dispose();
          } catch (e) {
            console.warn('[Molstar] stale init dispose failed', e);
          }
          return;
        }

        markInitPhase('plugin-ui-ready');
        clearTimeout(initTimeout);
        console.log('[Molstar] createPluginUI: success');

        pluginRef.current = pluginInstance;
        setPlugin(pluginInstance);
        setStorePlugin(pluginInstance);
        setIsInitialized(true);
        markInitPhase('plugin-stored');
        console.log('[Molstar] initViewer: plugin stored and initialized');

        // Double-click detection built on top of the click event
        let lastClickAt = 0;
        pluginInstance.behaviors.interaction.click.subscribe((e: any) => {
          const now = Date.now();
          const isDouble = now - lastClickAt < 350; // ms threshold
          lastClickAt = now;
          if (!isDouble) return;
          try {
            const loci = e?.current?.loci;
            if (!loci) return;
            if (StructureElement.Loci.is(loci) && loci.elements.length > 0) {
              // Resolve the exact picked location from the loci
              const first = StructureElement.Loci.getFirstLocation(loci);
              if (!first) return;
              const loc = first;

              // Prefer label (canonical) identifiers for stable display
              const compId = StructureProperties.atom.label_comp_id(loc);
              const labelSeqId = StructureProperties.residue.label_seq_id(loc);
              const authSeqId = StructureProperties.residue.auth_seq_id(loc);
              const insCode = StructureProperties.residue.pdbx_PDB_ins_code(loc) || null;
              const labelAsymId = StructureProperties.chain.label_asym_id(loc) || null;
              const authAsymId = StructureProperties.chain.auth_asym_id(loc) || null;

              addSelection({
                kind: 'residue',
                pdbId: lastLoadedPdb || undefined,
                compId,
                labelSeqId: labelSeqId ?? null,
                authSeqId: insCode ? `${authSeqId}${insCode}` : authSeqId,
                insCode,
                labelAsymId,
                authAsymId,
              });
            }
          } catch (err) {
            console.warn('[Molstar] selection capture failed', err);
          }
        });

        // Priority 1: Run any queued code
        if (pendingCodeToRun && pendingCodeToRun.trim()) {
          markInitPhase('running-pending-code');
          try {
            setIsExecuting(true);
            const exec = new CodeExecutor(pluginInstance);
            // Add timeout for code execution to prevent infinite loading
            const executionPromise = exec.executeCode(pendingCodeToRun);
            const timeoutPromise = new Promise<never>((_, reject) =>
              setTimeout(() => reject(new Error('Code execution timeout after 30 seconds')), 30000)
            );
            const result = await Promise.race([executionPromise, timeoutPromise]);
            clearErrorOnSuccess(result);
            setActivePane('viewer');
          } catch (e) {
            setErrorIfPdbNotFound(e);
            console.error('[Molstar] pending code execution failed', e);
          } finally {
            setIsExecuting(false);
            setPendingCodeToRun(null);
            await endLoading();
          }
          return;
        }

        // Priority 2: Get code to execute (prioritizes message code)
        // getCode() uses shared utility that filters out blob URLs automatically
        const codeToExecute = getCode();
        if (codeToExecute) {
          markInitPhase('running-restored-code');
          try {
            setIsExecuting(true);
            const exec = new CodeExecutor(pluginInstance);
            // Add timeout for code execution to prevent infinite loading
            const executionPromise = exec.executeCode(codeToExecute);
            const timeoutPromise = new Promise<never>((_, reject) =>
              setTimeout(() => reject(new Error('Code execution timeout after 30 seconds')), 30000)
            );
            const result = await Promise.race([executionPromise, timeoutPromise]);
            clearErrorOnSuccess(result);
            // Sync to store if it came from message
            if (!currentCode || currentCode.trim() === '') {
              setCurrentCode(codeToExecute);
            }
            setActivePane('viewer');
            lastExecutedCodeRef.current = codeToExecute;
          } catch (e) {
            setErrorIfPdbNotFound(e);
            console.error('[Molstar] execute code on mount failed', e);
          } finally {
            setIsExecuting(false);
            await endLoading();
          }
          return;
        }

        // Viewer initialized - code will be executed when it becomes available
        markInitPhase('initialized-waiting-code');
        console.log('[Molstar] initViewer: viewer initialized (waiting for code)');
        
      } catch (error) {
        console.error('[Molstar] initViewer: failed', error);
        setInitFailed(true);
        markInitPhase('failed');
      } finally {
        await endLoading();
        initInProgressRef.current = false;
        markInitPhase('end');
        console.log('[Molstar] initViewer: end (loading=false)');
      }
    };

    void initViewer();

    return () => {
      mountedRef.current = false;
      console.log('[Molstar] cleanup: start');
      const instance = pluginRef.current;
      if (instance) {
        try {
          instance.dispose();
          console.log('[Molstar] cleanup: plugin disposed');
        } catch (e) {
          console.warn('[Molstar] cleanup: dispose failed', e);
        }
        pluginRef.current = null;
        setStorePlugin(null);
      }
      // Clear container so next init uses a fresh DOM node (avoids createRoot warning on remount)
      if (containerRef.current?.firstChild) {
        containerRef.current.replaceChildren();
      }
      initInProgressRef.current = false;
      loadingStateRef.current = 'idle';
      console.log('[Molstar] cleanup: end');
    };
  }, []); // Only initialize once on mount

  // Unused function - kept for potential future use
  // @ts-ignore - intentionally unused
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const _loadDefaultStructure = async (pluginInstance: PluginUIContext) => {
    try {
      console.log('[Molstar] loadDefaultStructure: start');
      console.time('[Molstar] download');
      const data = await pluginInstance.builders.data.download({
        url: 'https://files.rcsb.org/view/1CBS.pdb',
        isBinary: false,
      });
      console.timeEnd('[Molstar] download');

      console.time('[Molstar] parseTrajectory');
      const trajectory = await pluginInstance.builders.structure.parseTrajectory(data, 'pdb');
      console.timeEnd('[Molstar] parseTrajectory');

      console.time('[Molstar] createModel');
      const model = await pluginInstance.builders.structure.createModel(trajectory);
      console.timeEnd('[Molstar] createModel');

      console.time('[Molstar] createStructure');
      const structure = await pluginInstance.builders.structure.createStructure(model);
      console.timeEnd('[Molstar] createStructure');

      console.time('[Molstar] addRepresentation');
      await pluginInstance.builders.structure.representation.addRepresentation(structure, {
        type: 'cartoon',
        color: 'secondary-structure'
      });
      console.timeEnd('[Molstar] addRepresentation');

      // Record default PDB in store so SelectionContext has a PDB
      try {
        const state = useAppStore.getState?.();
        if (state?.setLastLoadedPdb) state.setLastLoadedPdb('1CBS');
        
        // Also set the current code so the backend knows what structure is loaded
        if (state?.setCurrentCode && (!state.currentCode || state.currentCode.trim() === '')) {
          const defaultCode = `try {
  await builder.loadStructure('1CBS');
  await builder.addCartoonRepresentation({ color: 'secondary-structure' });
  builder.focusView();
} catch (e) { console.error(e); }`;
          state.setCurrentCode(defaultCode);
        }
      } catch {}

      console.log('[Molstar] loadDefaultStructure: done');
    } catch (error) {
      console.error('[Molstar] loadDefaultStructure: failed', error);
    }
  };

  // Re-run current editor code whenever viewer is mounted/ready and code changes
  useEffect(() => {
    const run = async () => {
      if (!plugin || !isInitialized) return;
      
      // Get code to execute (prioritizes message code over global code)
      // getCode() uses shared utility that filters out blob URLs automatically
      let code = getCode();
      
      if (!code) return;
      if (lastExecutedCodeRef.current === code) return;
      
      // Double-check for blob URLs (safety check)
      if (hasBlobUrl(code)) {
        console.warn('[Molstar] Re-execute: Code contains blob URL (expired), skipping');
        // Clear the stale code
        if (currentCode === code) {
          setCurrentCode('');
        }
        return;
      }
      
      // Sync to store if it came from message
      if (code !== currentCode) {
        setCurrentCode(code);
      }
      
      try {
        setIsExecuting(true);
        const exec = new CodeExecutor(plugin);
        const result = await exec.executeCode(code);
        clearErrorOnSuccess(result);
        lastExecutedCodeRef.current = code;
      } catch (e) {
        setErrorIfPdbNotFound(e);
        console.error('[Molstar] re-execute currentCode failed', e);
      } finally {
        setIsExecuting(false);
      }
    };
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plugin, isInitialized, currentCode, activeSessionId]);

  return (
    <div className="h-full w-full flex flex-col bg-gray-900">
      {/* Chimera-style Select/Actions Toolbar */}
      <MolstarToolbar plugin={plugin} />
      
      {/* Molstar Viewer Container */}
      <div className="flex-1 relative molstar-container">
        <style>{`
          .molstar-container .msp-plugin {
            position: absolute !important;
            inset: 0 !important;
            width: 100% !important;
            height: 100% !important;
          }
          .molstar-container .msp-layout-expanded {
            position: absolute !important;
            inset: 0 !important;
          }
        `}</style>
        {isLoading && (
          <div
            className={`absolute inset-0 z-10 transition-opacity ${isLoadingExiting ? 'opacity-0' : 'opacity-100'}`}
            style={{ transitionDuration: `${SKELETON_FADE_MS}ms` }}
          >
            <MolstarSkeleton message="Initializing Mol* viewer..." />
          </div>
        )}

        <div 
          ref={containerRef} 
          className="absolute inset-0 h-full w-full"
        />

        {pdbLoadError && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-gray-900/80 p-4">
            <div className="max-w-md rounded-lg bg-gray-800 p-4 shadow-xl ring-1 ring-gray-700">
              <h3 className="mb-2 text-sm font-semibold text-red-400">Structure could not be loaded</h3>
              <p className="mb-3 text-sm text-gray-200">
                {pdbLoadError.pdbId ? (
                  <>PDB ID <strong className="font-mono">{pdbLoadError.pdbId}</strong> was not found. The AI may have used an invalid or hallucinated ID.</>
                ) : (
                  <>This PDB ID doesn&apos;t exist. The AI may have hallucinated it.</>
                )}
              </p>
              <a
                href="https://www.rcsb.org/search"
                target="_blank"
                rel="noopener noreferrer"
                className="mb-3 inline-block text-sm text-blue-400 hover:underline"
              >
                Search RCSB PDB for a valid structure →
              </a>
              <button
                type="button"
                onClick={() => setPdbLoadError(null)}
                className="w-full rounded bg-gray-700 py-2 text-sm font-medium text-white hover:bg-gray-600"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {!isLoading && !isInitialized && initFailed && (
          <div className="absolute inset-0 bg-gray-900 flex items-center justify-center">
            <div className="text-white text-center">
              <div className="text-red-400 mb-2">Failed to initialize Molstar viewer</div>
              <div className="text-sm text-gray-400">Please refresh the page to try again</div>
            </div>
          </div>
        )}

        {isDev && (
          <div className="absolute left-2 top-2 z-30 rounded bg-black/55 px-2 py-1 text-[11px] text-gray-200 pointer-events-none">
            <span className="font-mono">mol* init #{debugInit.attempt}</span>
            <span className="mx-1">|</span>
            <span>{debugInit.phase}</span>
            {debugInit.at && (
              <>
                <span className="mx-1">|</span>
                <span>{debugInit.at}</span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Confidence score (pLDDT) panel below viewer when showing predicted structure */}
      {currentStructureOrigin?.type === 'alphafold' && <ConfidenceScorePanel />}
    </div>
  );
};