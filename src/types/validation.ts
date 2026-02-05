export interface ValidationReport {
  action: 'validation_result';
  source: string;
  grade: string;
  overall_score: number;

  // pLDDT metrics
  plddt_mean: number;
  plddt_median: number;
  plddt_high_confidence: number;
  plddt_low_confidence: number;
  plddt_per_residue: ResidueConfidence[];

  // Ramachandran
  rama_favored: number;
  rama_allowed: number;
  rama_outlier: number;
  rama_total: number;
  rama_favored_pct: number;
  rama_outlier_pct: number;
  rama_data: RamachandranPoint[];

  // Clashes
  clash_count: number;
  clash_details: ClashDetail[];

  // Summary
  total_residues: number;
  chains: string[];
  suggestions: ValidationSuggestion[];
  residue_metrics: ResidueMetric[];
}

export interface ResidueConfidence {
  chain_id: string;
  residue_number: number;
  residue_name: string;
  plddt: number;
}

export interface RamachandranPoint {
  phi: number;
  psi: number;
  chain_id: string;
  residue_number: number;
  residue_name: string;
  region: 'favored' | 'allowed' | 'outlier';
}

export interface ClashDetail {
  atom1: string;
  atom2: string;
  distance: number;
}

export interface ResidueMetric {
  chain_id: string;
  residue_number: number;
  residue_name: string;
  plddt: number | null;
  phi: number | null;
  psi: number | null;
  rama_region: string;
  clashes: number;
}

export interface ValidationSuggestion {
  type: 'confidence' | 'geometry' | 'clashes' | 'success' | 'error';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  detail: string;
  action: string;
  residues: Record<string, any>[];
}
