import { create } from 'zustand';
import { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';

interface AppState {
  activePane: 'viewer' | 'editor';
  plugin: PluginUIContext | null;
  currentCode: string;
  isExecuting: boolean;
  lastLoadedPdb: string | null;
  
  setActivePane: (pane: 'viewer' | 'editor') => void;
  setPlugin: (plugin: PluginUIContext | null) => void;
  setCurrentCode: (code: string) => void;
  setIsExecuting: (executing: boolean) => void;
  setLastLoadedPdb: (pdb: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activePane: 'viewer',
  plugin: null,
  currentCode: '',
  isExecuting: false,
  lastLoadedPdb: null,
  
  setActivePane: (pane) => set({ activePane: pane }),
  setPlugin: (plugin) => set({ plugin }),
  setCurrentCode: (code) => set({ currentCode: code }),
  setIsExecuting: (executing) => set({ isExecuting: executing }),
  setLastLoadedPdb: (pdb) => set({ lastLoadedPdb: pdb }),
}));