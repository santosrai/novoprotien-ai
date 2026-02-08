import { PluginUIContext } from 'molstar/lib/mol-plugin-ui/context';
import { getCurrentStructure } from './molstarSelections';

export interface StructureMetadata {
  sequence?: string;
  sequences?: Array<{ chain: string; sequence: string; length: number }>;
  residueCount?: number;
  chainCount?: number;
  chains?: string[];
  residueComposition?: Record<string, number>;
  isPolyGlycine?: boolean;
  structureType?: 'protein' | 'nucleic' | 'mixed' | 'unknown';
}

/**
 * Convert three-letter amino acid code to one-letter
 */
function threeToOneLetter(threeLetter: string): string | null {
  const map: Record<string, string> = {
    'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
    'GLN': 'Q', 'GLU': 'E', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
    'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
    'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V',
  };
  return map[threeLetter.trim().toUpperCase()] || null;
}

function isAminoAcid(residue: string): boolean {
  const aminoAcids = ['ALA', 'ARG', 'ASN', 'ASP', 'CYS', 'GLN', 'GLU', 'GLY', 'HIS', 'ILE',
    'LEU', 'LYS', 'MET', 'PHE', 'PRO', 'SER', 'THR', 'TRP', 'TYR', 'VAL'];
  return aminoAcids.includes(residue.trim().toUpperCase());
}

function isNucleicAcid(residue: string): boolean {
  const nucleicAcids = ['A', 'T', 'G', 'C', 'U', 'DA', 'DT', 'DG', 'DC', 'DU', 'ADE', 'THY', 'GUA', 'CYT', 'URA'];
  return nucleicAcids.includes(residue.trim().toUpperCase());
}

/**
 * Extract comprehensive structure metadata from the current MolStar viewer
 */
export async function extractStructureMetadata(
  plugin: PluginUIContext
): Promise<StructureMetadata | null> {
  if (!plugin) return null;

  try {
    const structure = getCurrentStructure(plugin);
    if (!structure) return null;

    const metadata: StructureMetadata = {
      chains: [],
      sequences: [],
      residueComposition: {},
    };

    const { units } = structure;
    const chainSequences = new Map<string, string>();
    const chainResidueCounts = new Map<string, number>();
    const residueComposition = new Map<string, number>();
    const chainSet = new Set<string>();

    // Iterate through units to extract sequence and composition
    for (const unit of units) {
      if (unit.kind === 0) { // atomic unit
        const { elements } = unit;
        const { model } = unit;
        
        // Access properties from model hierarchy
        // Use atom properties since residue properties may not be directly accessible
        const compIdProp = model.atomicHierarchy.atoms.label_comp_id;
        const asymIdProp = model.atomicHierarchy.chains.label_asym_id;
        const seqIdProp = model.atomicHierarchy.residues.label_seq_id;
        const residueAtomSegments = model.atomicHierarchy.residueAtomSegments;
        const chainAtomSegments = model.atomicHierarchy.chainAtomSegments;
        
        // Track residues per chain to build sequences
        const chainResidueMap = new Map<string, Map<number, string>>();
        
        for (let i = 0; i < elements.length; i++) {
          const element = elements[i];
          
          // Get residue and chain indices from atom index
          const residueIdx = residueAtomSegments.index[element];
          const chainIdx = chainAtomSegments.index[element];
          
          // Get residue and chain information
          // Use atom's comp_id (all atoms in a residue have the same comp_id)
          const compId = compIdProp.value(element);
          const asymId = asymIdProp.value(chainIdx);
          const seqId = seqIdProp.value(residueIdx);
          
          if (!compId || !asymId || seqId === null || seqId === undefined) continue;
          
          // Track chain
          chainSet.add(asymId);
          
          // Build sequence per chain, avoiding duplicates for same seq_id
          if (!chainResidueMap.has(asymId)) {
            chainResidueMap.set(asymId, new Map());
          }
          const chainResidues = chainResidueMap.get(asymId)!;
          
          // Only add each residue once (by seq_id)
          if (!chainResidues.has(seqId)) {
            chainResidues.set(seqId, compId);
            
            // Count residue composition
            const count = residueComposition.get(compId) || 0;
            residueComposition.set(compId, count + 1);
          }
        }
        
        // Convert chain residue maps to sequences
        for (const [chainId, residues] of chainResidueMap.entries()) {
          // Sort by sequence ID and build sequence
          const sortedResidues = Array.from(residues.entries())
            .sort((a, b) => a[0] - b[0])
            .map(([_, compId]) => compId);
          
          // Convert to one-letter codes
          const oneLetterSeq = sortedResidues
            .map(threeLetter => threeToOneLetter(threeLetter))
            .filter((letter): letter is string => letter !== null)
            .join('');
          
          if (oneLetterSeq.length > 0) {
            chainSequences.set(chainId, oneLetterSeq);
            chainResidueCounts.set(chainId, oneLetterSeq.length);
          }
        }
      }
    }

    // Convert to arrays
    metadata.chains = Array.from(chainSet).sort();
    metadata.sequences = Array.from(chainSequences.entries()).map(([chain, seq]) => ({
      chain,
      sequence: seq,
      length: seq.length,
    }));

    // Combine sequences if single chain
    if (metadata.sequences.length === 1) {
      metadata.sequence = metadata.sequences[0].sequence;
    }

    // Calculate totals
    metadata.residueCount = Array.from(residueComposition.values()).reduce((a, b) => a + b, 0);
    metadata.chainCount = metadata.chains.length;

    // Convert residue composition
    metadata.residueComposition = Object.fromEntries(residueComposition);

    // Detect poly-glycine
    if (metadata.sequence) {
      const uniqueResidues = new Set(metadata.sequence.split(''));
      metadata.isPolyGlycine = uniqueResidues.size === 1 && uniqueResidues.has('G');
    }

    // Determine structure type
    const allResidues = Array.from(residueComposition.keys());
    const hasProtein = allResidues.some(r => isAminoAcid(r));
    const hasNucleic = allResidues.some(r => isNucleicAcid(r));
    
    if (hasProtein && hasNucleic) {
      metadata.structureType = 'mixed';
    } else if (hasProtein) {
      metadata.structureType = 'protein';
    } else if (hasNucleic) {
      metadata.structureType = 'nucleic';
    } else {
      metadata.structureType = 'unknown';
    }

    return metadata;
  } catch (error) {
    console.error('[StructureMetadata] Error extracting metadata:', error);
    return null;
  }
}

/**
 * Summarize structure metadata for sending to the agent.
 * Strips full sequences and truncates composition to reduce payload size.
 * Backend still applies final truncation.
 */
export function summarizeForAgent(metadata: StructureMetadata | null): StructureMetadata | null {
  if (!metadata) return null;

  const result: StructureMetadata = {
    chains: metadata.chains,
    chainCount: metadata.chainCount,
    residueCount: metadata.residueCount,
    structureType: metadata.structureType,
  };

  // Keep sequences as chain + length only (no full sequence strings)
  if (metadata.sequences && metadata.sequences.length > 0) {
    result.sequences = metadata.sequences.map(({ chain, length }) => ({
      chain,
      sequence: '', // Omit to reduce payload
      length,
    }));
  }

  // Truncate residue composition to top 5
  if (metadata.residueComposition && Object.keys(metadata.residueComposition).length > 0) {
    const sorted = Object.entries(metadata.residueComposition)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5);
    result.residueComposition = Object.fromEntries(sorted);
  }

  return result;
}

