import { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';
import { getPDBUrl, validatePDBId, checkPDBExists } from './pdbUtils';
import { getAuthHeaders } from './api';

export interface ResidueSelector {
  label_asym_id?: string;
  label_seq_id?: number;
  auth_asym_id?: string;
  auth_seq_id?: number;
}

export interface AlignmentResult {
  rmsd: number;
  alignedLength: number;
  alignmentScore: number;
}

export interface MolstarBuilder {
  loadStructure: (pdbId: string) => Promise<void>;
  loadStructureFromContent: (content: string, format: 'pdb' | 'sdf') => Promise<void>;
  loadAdditionalStructure: (content: string, format?: 'pdb' | 'sdf') => Promise<any>;
  alignStructures: (structure1: any, structure2: any) => Promise<AlignmentResult>;
  addCartoonRepresentation: (options?: any) => Promise<void>;
  addBallAndStickRepresentation: (options?: any) => Promise<void>;
  addSurfaceRepresentation: (options?: any) => Promise<void>;
  addWaterRepresentation: (options?: any) => Promise<void>;
  highlightLigands: (options?: any) => Promise<void>;
  focusView: () => void;
  clearStructure: () => Promise<void>;
  // New selector-based methods
  highlightResidue: (selector: ResidueSelector, options?: { color?: string }) => Promise<void>;
  labelResidue: (selector: ResidueSelector, text: string) => Promise<void>;
  focusResidue: (selector: ResidueSelector) => Promise<void>;
  colorByConfidence: () => Promise<void>;
}

export const createMolstarBuilder = (
  plugin: PluginUIContext,
  onPdbLoaded?: (pdbId: string) => void
): MolstarBuilder => {
  let currentStructure: any = null;

  return {
    async loadStructure(pdbIdOrUrl: string) {
      // Check if it's a URL (http, https, blob, or data URL)
      const isUrl = pdbIdOrUrl.startsWith('http://') || 
                    pdbIdOrUrl.startsWith('https://') || 
                    pdbIdOrUrl.startsWith('blob:') ||
                    pdbIdOrUrl.startsWith('data:') ||
                    pdbIdOrUrl.startsWith('/api/');

      // Check if this is an internal API URL that needs authentication
      const isApiUrl = pdbIdOrUrl.startsWith('/api/');
      
      // If it's not a URL, validate as PDB ID
      if (!isUrl && !validatePDBId(pdbIdOrUrl)) {
        throw new Error(`Invalid PDB ID or URL: ${pdbIdOrUrl}`);
      }

      // For PDB IDs, check existence in RCSB before downloading (avoids 404 on hallucinated IDs)
      if (!isUrl) {
        try {
          const exists = await checkPDBExists(pdbIdOrUrl);
          if (!exists) {
            throw new Error(`PDB ID "${pdbIdOrUrl}" was not found in the RCSB database. It may be invalid or hallucinated. Search at https://www.rcsb.org/search`);
          }
        } catch (e) {
          if (e instanceof Error && e.message.includes('not found in the RCSB database')) throw e;
          // Network or other error: fall through to normal download
        }
      }

      try {
        // Always clear any existing structures in the scene before loading a new one.
        // This avoids having multiple proteins displayed at once if a default or
        // previous structure was loaded outside of this builder's lifecycle.
        await this.clearStructure();

        let data: any;
        // rawText is saved for the API URL path so we can re-create a fresh
        // Molstar data state if the PDB parse fails and we need to retry as SDF.
        let rawText: string | undefined;

        if (isApiUrl) {
          // For internal API URLs, fetch with authentication headers since
          // MolStar's built-in download doesn't include JWT tokens.
          const headers = getAuthHeaders();
          const response = await fetch(pdbIdOrUrl, { headers });
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }
          rawText = await response.text();
          // Create a blob URL from the fetched data so MolStar's download()
          // processes it through its standard pipeline (same as external PDB files).
          const blob = new Blob([rawText], { type: 'text/plain' });
          const blobUrl = URL.createObjectURL(blob);
          try {
            data = await plugin.builders.data.download({
              url: blobUrl,
              isBinary: false,
            });
          } finally {
            URL.revokeObjectURL(blobUrl);
          }
        } else {
          // Use URL directly if it's a URL, otherwise convert PDB ID to URL
          const url = isUrl ? pdbIdOrUrl : getPDBUrl(pdbIdOrUrl);
          data = await plugin.builders.data.download({
            url,
            isBinary: false,
          });
        }

        let trajectory: any;
        try {
          trajectory = await plugin.builders.structure.parseTrajectory(data, 'pdb');
        } catch {
          // When parseTrajectory fails, Molstar tears down the data StateObject node,
          // making data.ref undefined. Re-using the same `data` for the SDF retry
          // causes "Cannot read properties of undefined (reading 'ref')".
          // Fix: create a FRESH data state before retrying with SDF format.
          let data2: any;
          if (rawText !== undefined) {
            // isApiUrl path — reuse already-fetched text to avoid a second network request
            const blob2 = new Blob([rawText], { type: 'text/plain' });
            const blobUrl2 = URL.createObjectURL(blob2);
            try {
              data2 = await plugin.builders.data.download({ url: blobUrl2, isBinary: false });
            } finally {
              URL.revokeObjectURL(blobUrl2);
            }
          } else {
            // External / blob URL path — re-download from the original URL.
            // Blob URLs remain valid until explicitly revoked, so this is safe.
            const url = isUrl ? pdbIdOrUrl : getPDBUrl(pdbIdOrUrl);
            data2 = await plugin.builders.data.download({ url, isBinary: false });
          }
          trajectory = await plugin.builders.structure.parseTrajectory(data2, 'sdf');
        }
        const model = await plugin.builders.structure.createModel(trajectory);
        currentStructure = await plugin.builders.structure.createStructure(model);
        
        // Only call onPdbLoaded callback if it was a PDB ID (not a URL)
        if (!isUrl && onPdbLoaded) {
          onPdbLoaded(pdbIdOrUrl);
        }

        return currentStructure;
      } catch (error) {
        throw new Error(`Failed to load structure ${pdbIdOrUrl}: ${error}`);
      }
    },

    async loadStructureFromContent(content: string, format: 'pdb' | 'sdf') {
      if (!content || !content.trim()) {
        throw new Error('Content is required for loadStructureFromContent');
      }
      try {
        await this.clearStructure();

        const blob = new Blob([content], { type: 'text/plain' });
        const blobUrl = URL.createObjectURL(blob);
        let data: any;
        try {
          data = await plugin.builders.data.download({
            url: blobUrl,
            isBinary: false,
          });
        } finally {
          URL.revokeObjectURL(blobUrl);
        }

        const trajectory = await plugin.builders.structure.parseTrajectory(data, format);
        const model = await plugin.builders.structure.createModel(trajectory);
        currentStructure = await plugin.builders.structure.createStructure(model);

        await plugin.builders.structure.representation.addRepresentation(
          currentStructure,
          { type: 'ball-and-stick' as const, color: 'element-symbol' as const }
        );
        this.focusView();

        return currentStructure;
      } catch (error) {
        throw new Error(`Failed to load structure from content (${format}): ${error}`);
      }
    },

    async loadAdditionalStructure(content: string, format: 'pdb' | 'sdf' = 'pdb') {
      if (!content || !content.trim()) {
        throw new Error('Content is required for loadAdditionalStructure');
      }
      try {
        // Load WITHOUT clearing existing structures
        const blob = new Blob([content], { type: 'text/plain' });
        const blobUrl = URL.createObjectURL(blob);
        let data: any;
        try {
          data = await plugin.builders.data.download({
            url: blobUrl,
            isBinary: false,
          });
        } finally {
          URL.revokeObjectURL(blobUrl);
        }

        const trajectory = await plugin.builders.structure.parseTrajectory(data, format);
        const model = await plugin.builders.structure.createModel(trajectory);
        const structure = await plugin.builders.structure.createStructure(model);

        return structure;
      } catch (error) {
        throw new Error(`Failed to load additional structure (${format}): ${error}`);
      }
    },

    async alignStructures(structure1: any, structure2: any): Promise<AlignmentResult> {
      try {
        // Use Molstar's built-in sequence alignment + RMSD superposition
        const { alignAndSuperpose } = await import('molstar/lib/mol-model/structure/structure/util/superposition');
        const { StructureElement } = await import('molstar/lib/mol-model/structure/structure/element');
        const { StateTransforms } = await import('molstar/lib/mol-plugin-state/transforms');

        const data1 = structure1.cell?.obj?.data;
        const data2 = structure2.cell?.obj?.data;

        if (!data1 || !data2) {
          throw new Error('Could not access structure data for alignment');
        }

        // Get whole-structure loci for both structures
        const loci1 = StructureElement.Loci.all(data1);
        const loci2 = StructureElement.Loci.all(data2);

        // Run sequence alignment + RMSD superposition (uses BLOSUM62 for proteins)
        const results = alignAndSuperpose([loci1, loci2]);

        if (results.length === 0) {
          throw new Error('Alignment produced no results');
        }

        const result = results[0]; // { bTransform, rmsd, alignmentScore }

        // Apply transformation to structure2 to superpose onto structure1
        const b = plugin.state.data.build().to(structure2)
          .insert(StateTransforms.Model.TransformStructureConformation, {
            transform: { name: 'matrix' as const, params: { data: result.bTransform, transpose: false } }
          });
        await plugin.runTask(plugin.state.data.updateTree(b));

        const alignedLen = Math.min(
          StructureElement.Loci.size(loci1),
          StructureElement.Loci.size(loci2)
        );

        console.log(`[Molstar] Superposition: RMSD=${result.rmsd.toFixed(2)}, alignmentScore=${result.alignmentScore.toFixed(1)}, aligned=${alignedLen}`);

        return {
          rmsd: result.rmsd,
          alignedLength: alignedLen,
          alignmentScore: result.alignmentScore,
        };
      } catch (error) {
        console.error('[Molstar] Superposition failed:', error);
        throw new Error(`Structure superposition failed: ${error}`);
      }
    },

    async addCartoonRepresentation(options = {}) {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      const defaultOptions = {
        type: 'cartoon' as const,
        color: 'secondary-structure' as const,
        ...options
      };

      await plugin.builders.structure.representation.addRepresentation(
        currentStructure,
        defaultOptions
      );
    },

    async addBallAndStickRepresentation(options = {}) {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      const defaultOptions = {
        type: 'ball-and-stick' as const,
        color: 'element' as const,
        ...options
      };

      await plugin.builders.structure.representation.addRepresentation(
        currentStructure,
        defaultOptions
      );
    },

    async addSurfaceRepresentation(options = {}) {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      const defaultOptions = {
        type: 'surface' as const,
        color: 'hydrophobicity' as const,
        alpha: 0.7,
        ...options
      };

      await plugin.builders.structure.representation.addRepresentation(
        currentStructure,
        defaultOptions
      );
    },

    async addWaterRepresentation(options = {}) {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      // Minimal water selection using label_resname = 'HOH' which is common for water in PDB
      const defaultOptions = {
        type: 'ball-and-stick' as const,
        color: 'element' as const,
        query: { kind: 'expression', expression: "label_resname = 'HOH'" },
        ...options
      };

      await plugin.builders.structure.representation.addRepresentation(
        currentStructure,
        defaultOptions
      );
    },

    async highlightLigands() {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      // This is a simplified implementation
      // In a real application, you would use proper selection queries
      await plugin.builders.structure.representation.addRepresentation(
        currentStructure,
        {
          type: 'ball-and-stick',
          color: 'element-symbol'
        }
      );
    },

    focusView() {
      if (currentStructure) {
        plugin.managers.camera.focusLoci(currentStructure);
      }
    },

    async clearStructure() {
      try {
        // Remove any known current structure first
        if (currentStructure) {
          await plugin.managers.structure.hierarchy.remove([currentStructure]);
          currentStructure = null;
        }

        // Additionally, ensure all existing root structures are removed
        const hierarchy = plugin.managers.structure.hierarchy;
        const existing = (hierarchy as any)?.current?.structures ?? [];
        if (Array.isArray(existing) && existing.length > 0) {
          await hierarchy.remove(existing as any);
        }
      } catch (e) {
        // Swallow errors to keep UX smooth; subsequent loads will overwrite
        console.warn('[Molstar] clearStructure failed, continuing', e);
      }
    },

    async highlightResidue(selector: ResidueSelector, options: { color?: string } = {}) {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      const { color = 'red' } = options;
      
      try {
        // Add ball-and-stick representation with color for the specific residue
        // Note: Full residue-specific selection would require more complex query implementation
        await plugin.builders.structure.representation.addRepresentation(currentStructure, {
          type: 'ball-and-stick',
          colorTheme: { name: 'uniform', params: { value: color } },
          sizeTheme: { name: 'uniform', params: { value: 1 } }
        });
        
        console.log(`Highlighted residue ${selector.label_asym_id}:${selector.label_seq_id}`);
      } catch (error) {
        console.warn('Failed to highlight residue:', error);
      }
    },

    async labelResidue(selector: ResidueSelector, text: string) {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      try {
        // For now, log the label request - proper label implementation requires more complex setup
        console.log(`Label request for ${selector.label_asym_id}:${selector.label_seq_id} - "${text}"`);
        
        // Note: Proper label implementation would require creating a custom label provider
        // This is a placeholder that demonstrates the interface
      } catch (error) {
        console.warn('Failed to label residue:', error);
      }
    },

    async focusResidue(selector: ResidueSelector) {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      try {
        // Focus on the entire structure for now - specific residue focusing requires
        // more complex implementation with proper structure queries
        plugin.managers.camera.focusLoci(currentStructure);
        console.log(`Focus request for residue ${selector.label_asym_id}:${selector.label_seq_id}`);
      } catch (error) {
        console.warn('Failed to focus residue:', error);
      }
    },

    async colorByConfidence() {
      if (!currentStructure) {
        throw new Error('No structure loaded');
      }

      try {
        // Clear existing representations
        const hierarchy = plugin.managers.structure.hierarchy;
        const existing = (hierarchy as any)?.current?.structures ?? [];
        if (Array.isArray(existing) && existing.length > 0) {
          for (const s of existing) {
            const components = s?.components ?? [];
            for (const comp of components) {
              const representations = comp?.representations ?? [];
              for (const repr of representations) {
                await plugin.managers.structure.hierarchy.remove([repr]);
              }
            }
          }
        }

        // Add cartoon with uncertainty (B-factor / pLDDT) coloring
        await plugin.builders.structure.representation.addRepresentation(
          currentStructure,
          {
            type: 'cartoon' as const,
            color: 'uncertainty' as const,
          }
        );

        console.log('[Molstar] Colored by confidence (B-factor/pLDDT)');
      } catch (error) {
        console.warn('Failed to color by confidence:', error);
        // Fallback: just re-apply cartoon with element coloring
        await plugin.builders.structure.representation.addRepresentation(
          currentStructure,
          {
            type: 'cartoon' as const,
            color: 'element-symbol' as const,
          }
        );
      }
    }
  };
};

export const generateVisualizationCode = (
  proteinName: string,
  pdbId: string,
  options: {
    representation?: 'cartoon' | 'surface' | 'ball-and-stick';
    colorScheme?: string;
    showLigands?: boolean;
  } = {}
): string => {
  const { representation = 'cartoon', colorScheme = 'secondary-structure', showLigands = true } = options;

  return `// Visualizing ${proteinName} (${pdbId})
async function visualizeProtein() {
  try {
    // Load the structure
    await builder.loadStructure('${pdbId}');
    
    // Add ${representation} representation
    await builder.add${representation.charAt(0).toUpperCase() + representation.slice(1)}Representation({
      color: '${colorScheme}'
    });
    
    ${showLigands ? '// Highlight ligands\n    await builder.highlightLigands();' : ''}
    
    // Focus the view
    builder.focusView();
    
    console.log('Successfully loaded ${proteinName}');
  } catch (error) {
    console.error('Failed to visualize protein:', error);
  }
}

// Execute the visualization
visualizeProtein();`;
};