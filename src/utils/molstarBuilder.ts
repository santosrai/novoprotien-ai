import { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';
import { getPDBUrl, validatePDBId } from './pdbUtils';

export interface MolstarBuilder {
  loadStructure: (pdbId: string) => Promise<void>;
  addCartoonRepresentation: (options?: any) => Promise<void>;
  addBallAndStickRepresentation: (options?: any) => Promise<void>;
  addSurfaceRepresentation: (options?: any) => Promise<void>;
  highlightLigands: () => Promise<void>;
  focusView: () => void;
  clearStructure: () => Promise<void>;
}

export const createMolstarBuilder = (plugin: PluginUIContext): MolstarBuilder => {
  let currentStructure: any = null;

  return {
    async loadStructure(pdbId: string) {
      if (!validatePDBId(pdbId)) {
        throw new Error(`Invalid PDB ID: ${pdbId}`);
      }

      try {
        const url = getPDBUrl(pdbId);
        
        const data = await plugin.builders.data.download({
          url,
          isBinary: false,
        });

        const trajectory = await plugin.builders.structure.parseTrajectory(data, 'pdb');
        const model = await plugin.builders.structure.createModel(trajectory);
        currentStructure = await plugin.builders.structure.createStructure(model);

        return currentStructure;
      } catch (error) {
        throw new Error(`Failed to load structure ${pdbId}: ${error}`);
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
          color: { name: 'uniform', params: { value: 0xff6b6b } }
        }
      );
    },

    focusView() {
      if (currentStructure) {
        plugin.managers.camera.focusLoci(currentStructure);
      }
    },

    async clearStructure() {
      if (currentStructure) {
        await plugin.managers.structure.hierarchy.remove([currentStructure]);
        currentStructure = null;
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