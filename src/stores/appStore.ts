import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';

export interface SelectionContext {
  pdbId?: string;
  kind: 'residue';
  compId?: string; // residue name, e.g., GLU
  authSeqId?: number | string | null; // residue number; can include insertion code (e.g., 16B)
  insCode?: string | null; // insertion code
  // Chain and residue identifiers in both label and author namespaces
  labelAsymId?: string | null; // preferred chain id for display
  authAsymId?: string | null; // author chain id
  labelSeqId?: number | string | null; // preferred residue index for display
  mutation?: {
    toCompId: string; // target 3-letter residue code, e.g., ALA
  } | null;
}

interface AppState {
  activePane: 'viewer' | 'editor';
  plugin: PluginUIContext | null;
  currentCode: string;
  isExecuting: boolean;
  lastLoadedPdb: string | null;
  pendingCodeToRun: string | null;
  selection: SelectionContext | null;
  
  setActivePane: (pane: 'viewer' | 'editor') => void;
  setPlugin: (plugin: PluginUIContext | null) => void;
  setCurrentCode: (code: string) => void;
  setIsExecuting: (executing: boolean) => void;
  setLastLoadedPdb: (pdb: string | null) => void;
  setPendingCodeToRun: (code: string | null) => void;
  setSelection: (selection: SelectionContext | null) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      activePane: 'viewer',
      plugin: null,
      currentCode: '',
      isExecuting: false,
      lastLoadedPdb: null,
      pendingCodeToRun: null,
      selection: null,
      
      setActivePane: (pane) => set({ activePane: pane }),
      setPlugin: (plugin) => set({ plugin }),
      setCurrentCode: (code) => set({ currentCode: code }),
      setIsExecuting: (executing) => set({ isExecuting: executing }),
      setLastLoadedPdb: (pdb) => set({ lastLoadedPdb: pdb }),
      setPendingCodeToRun: (code) => set({ pendingCodeToRun: code }),
      setSelection: (selection) => set({ selection }),
    }),
    {
      name: 'novoprotein-app-storage',
      version: 1,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        activePane: state.activePane,
        currentCode: state.currentCode,
        lastLoadedPdb: state.lastLoadedPdb,
        // selection is session state; do not persist to avoid stale highlights
        // Do not persist transient execution code
      }),
    }
  )
);