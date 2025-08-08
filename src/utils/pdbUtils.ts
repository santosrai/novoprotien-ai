import axios from 'axios';

export interface PDBSearchResult {
  identifier: string;
  title: string;
  experimental_method: string[];
  resolution?: number;
}

export const searchPDB = async (query: string): Promise<PDBSearchResult[]> => {
  try {
    const response = await axios.post('https://search.rcsb.org/rcsbsearch/v2/query', {
      query: {
        type: 'terminal',
        service: 'text',
        parameters: {
          attribute: 'rcsb_struct_keywords.pdbx_keywords',
          operator: 'contains_phrase',
          value: query
        }
      },
      return_type: 'entry',
      request_options: {
        paginate: {
          start: 0,
          rows: 10
        }
      }
    });

    return response.data.result_set || [];
  } catch (error) {
    console.error('PDB search failed:', error);
    return [];
  }
};

export const resolvePDBFromName = async (name: string): Promise<string | null> => {
  const commonProteins: Record<string, string> = {
    'insulin': '1ZNI',
    'hemoglobin': '1HHO',
    'antibody': '1IGT',
    'dna': '1BNA',
    'lysozyme': '6LYZ',
    'myoglobin': '1MBN',
    'cytochrome': '1HRC',
    'collagen': '1CGD',
    'keratin': '1I7Q',
    'albumin': '1AO6'
  };

  const lowercaseName = name.toLowerCase();
  
  // Check common proteins first
  if (commonProteins[lowercaseName]) {
    return commonProteins[lowercaseName];
  }

  // If it looks like a PDB code (4 characters), return as is
  if (/^[0-9][A-Za-z0-9]{3}$/.test(name)) {
    return name.toUpperCase();
  }

  // Try searching PDB
  try {
    const results = await searchPDB(name);
    if (results.length > 0) {
      return results[0].identifier;
    }
  } catch (error) {
    console.error('Failed to search PDB:', error);
  }

  return null;
};

export const getPDBUrl = (pdbId: string): string => {
  return `https://files.rcsb.org/view/${pdbId.toUpperCase()}.pdb`;
};

export const validatePDBId = (pdbId: string): boolean => {
  return /^[0-9][A-Za-z0-9]{3}$/.test(pdbId);
};