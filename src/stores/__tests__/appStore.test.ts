import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '../appStore';

describe('appStore', () => {
  beforeEach(() => {
    // Reset the store to initial state before each test
    useAppStore.setState({
      activePane: null,
      plugin: null,
      currentCode: '',
      isExecuting: false,
      lastLoadedPdb: null,
      pendingCodeToRun: null,
      selections: [],
      chatPanelWidth: 400,
      isViewerVisible: false,
      currentStructureOrigin: null,
      selectedFile: null,
      molstarSelection: { count: 0 },
    });
  });

  describe('setActivePane', () => {
    it('sets the active pane', () => {
      useAppStore.getState().setActivePane('viewer');
      expect(useAppStore.getState().activePane).toBe('viewer');
    });

    it('can set active pane to null', () => {
      useAppStore.getState().setActivePane('editor');
      useAppStore.getState().setActivePane(null);
      expect(useAppStore.getState().activePane).toBeNull();
    });
  });

  describe('code execution state', () => {
    it('sets and gets currentCode', () => {
      useAppStore.getState().setCurrentCode('console.log("hello")');
      expect(useAppStore.getState().currentCode).toBe('console.log("hello")');
    });

    it('tracks isExecuting state', () => {
      expect(useAppStore.getState().isExecuting).toBe(false);
      useAppStore.getState().setIsExecuting(true);
      expect(useAppStore.getState().isExecuting).toBe(true);
    });
  });

  describe('PDB tracking', () => {
    it('tracks the last loaded PDB', () => {
      useAppStore.getState().setLastLoadedPdb('1HHO');
      expect(useAppStore.getState().lastLoadedPdb).toBe('1HHO');
    });

    it('can clear the last loaded PDB', () => {
      useAppStore.getState().setLastLoadedPdb('1HHO');
      useAppStore.getState().setLastLoadedPdb(null);
      expect(useAppStore.getState().lastLoadedPdb).toBeNull();
    });
  });

  describe('selections management', () => {
    it('starts with empty selections', () => {
      expect(useAppStore.getState().selections).toHaveLength(0);
    });

    it('adds a selection', () => {
      useAppStore.getState().addSelection({ kind: 'residue', compId: 'GLU', labelSeqId: 42 });
      expect(useAppStore.getState().selections).toHaveLength(1);
      expect(useAppStore.getState().selections[0].compId).toBe('GLU');
    });

    it('prevents duplicate selections', () => {
      const sel = { kind: 'residue' as const, compId: 'GLU', labelSeqId: 42, authSeqId: 42, labelAsymId: 'A', pdbId: '1HHO' };
      useAppStore.getState().addSelection(sel);
      useAppStore.getState().addSelection(sel);
      expect(useAppStore.getState().selections).toHaveLength(1);
    });

    it('removes a selection by index', () => {
      useAppStore.getState().addSelection({ kind: 'residue', compId: 'GLU' });
      useAppStore.getState().addSelection({ kind: 'residue', compId: 'ALA' });
      useAppStore.getState().removeSelection(0);
      expect(useAppStore.getState().selections).toHaveLength(1);
      expect(useAppStore.getState().selections[0].compId).toBe('ALA');
    });

    it('clears all selections', () => {
      useAppStore.getState().addSelection({ kind: 'residue', compId: 'GLU' });
      useAppStore.getState().addSelection({ kind: 'residue', compId: 'ALA' });
      useAppStore.getState().clearSelections();
      expect(useAppStore.getState().selections).toHaveLength(0);
    });

    it('sets selections array', () => {
      const sels = [
        { kind: 'residue' as const, compId: 'GLU' },
        { kind: 'residue' as const, compId: 'ALA' },
      ];
      useAppStore.getState().setSelections(sels);
      expect(useAppStore.getState().selections).toHaveLength(2);
    });
  });

  describe('backward compatibility (selection)', () => {
    it('setSelection with a value sets the first selection', () => {
      useAppStore.getState().setSelection({ kind: 'residue', compId: 'TRP' });
      expect(useAppStore.getState().selections).toHaveLength(1);
      expect(useAppStore.getState().selections[0].compId).toBe('TRP');
    });

    it('setSelection(null) clears selections', () => {
      useAppStore.getState().addSelection({ kind: 'residue', compId: 'GLU' });
      useAppStore.getState().setSelection(null);
      expect(useAppStore.getState().selections).toHaveLength(0);
    });
  });

  describe('molstar selection tracking', () => {
    it('tracks selection count', () => {
      useAppStore.getState().setMolstarSelectionCount(42);
      expect(useAppStore.getState().molstarSelection.count).toBe(42);
    });

    it('hasMolstarSelection returns true when count > 0', () => {
      useAppStore.getState().setMolstarSelectionCount(5);
      expect(useAppStore.getState().hasMolstarSelection()).toBe(true);
    });

    it('hasMolstarSelection returns false when count is 0', () => {
      expect(useAppStore.getState().hasMolstarSelection()).toBe(false);
    });

    it('records molstar actions', () => {
      const action = { type: 'color' as const, target: 'chain A', timestamp: Date.now() };
      useAppStore.getState().recordMolstarAction(action);
      expect(useAppStore.getState().molstarSelection.lastAction).toEqual(action);
    });
  });

  describe('viewer and layout', () => {
    it('tracks viewer visibility', () => {
      expect(useAppStore.getState().isViewerVisible).toBe(false);
      useAppStore.getState().setViewerVisible(true);
      expect(useAppStore.getState().isViewerVisible).toBe(true);
    });

    it('tracks chat panel width', () => {
      useAppStore.getState().setChatPanelWidth(600);
      expect(useAppStore.getState().chatPanelWidth).toBe(600);
    });
  });

  describe('structure origin', () => {
    it('sets and clears structure origin', () => {
      useAppStore.getState().setCurrentStructureOrigin({ type: 'pdb', pdbId: '1HHO' });
      expect(useAppStore.getState().currentStructureOrigin?.pdbId).toBe('1HHO');

      useAppStore.getState().setCurrentStructureOrigin(null);
      expect(useAppStore.getState().currentStructureOrigin).toBeNull();
    });
  });
});
