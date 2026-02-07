import { describe, it, expect } from 'vitest';
import {
  validateSequence,
  estimateFoldingTime,
  getDefaultParameters,
  parseSequenceInput,
  formatResultMetadata,
  type AlphaFoldParameters,
  type AlphaFoldResult,
} from '../alphafoldUtils';

describe('validateSequence', () => {
  it('accepts a valid amino acid sequence of sufficient length', () => {
    const result = validateSequence('ACDEFGHIKLMNPQRSTVWY'.repeat(2));
    expect(result.isValid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('rejects an empty sequence', () => {
    const result = validateSequence('');
    expect(result.isValid).toBe(false);
    expect(result.errors).toContain('Sequence cannot be empty');
  });

  it('rejects sequences with invalid amino acid characters', () => {
    const result = validateSequence('ACDEFGHIKLMNPQRSTVWYZ'.repeat(2));
    expect(result.isValid).toBe(false);
    expect(result.errors.some((e) => e.includes('Invalid amino acids'))).toBe(true);
  });

  it('rejects sequences shorter than 20 residues', () => {
    const result = validateSequence('ACDEFGHIK');
    expect(result.isValid).toBe(false);
    expect(result.errors.some((e) => e.includes('too short'))).toBe(true);
  });

  it('rejects sequences longer than 2000 residues', () => {
    const result = validateSequence('A'.repeat(2001));
    expect(result.isValid).toBe(false);
    expect(result.errors.some((e) => e.includes('too long'))).toBe(true);
  });

  it('strips whitespace before validation', () => {
    const seq = 'A C D E F G H I K L M N P Q R S T V W Y';
    const result = validateSequence(seq);
    expect(result.isValid).toBe(true);
  });
});

describe('estimateFoldingTime', () => {
  const defaultParams: AlphaFoldParameters = getDefaultParameters();

  it('returns a short estimate for sequences under 100 residues', () => {
    expect(estimateFoldingTime('A'.repeat(50), defaultParams)).toContain('2-5');
  });

  it('returns a medium estimate for sequences 100-300', () => {
    expect(estimateFoldingTime('A'.repeat(200), defaultParams)).toContain('5-15');
  });

  it('returns a longer estimate for sequences 300-600', () => {
    expect(estimateFoldingTime('A'.repeat(400), defaultParams)).toContain('15-30');
  });

  it('returns the longest estimate for sequences over 600', () => {
    expect(estimateFoldingTime('A'.repeat(800), defaultParams)).toContain('30-60');
  });

  it('appends relaxation info when enabled', () => {
    const params = { ...defaultParams, relax_prediction: true };
    expect(estimateFoldingTime('A'.repeat(50), params)).toContain('relaxation');
  });

  it('appends iteration multiplier when > 1', () => {
    const params = { ...defaultParams, iterations: 3 };
    expect(estimateFoldingTime('A'.repeat(50), params)).toContain('3');
  });
});

describe('getDefaultParameters', () => {
  it('returns sensible defaults', () => {
    const params = getDefaultParameters();
    expect(params.algorithm).toBe('mmseqs2');
    expect(params.e_value).toBe(0.0001);
    expect(params.iterations).toBe(1);
    expect(params.databases).toContain('small_bfd');
    expect(params.relax_prediction).toBe(false);
    expect(params.skip_template_search).toBe(true);
  });
});

describe('parseSequenceInput', () => {
  it('parses raw sequence input', () => {
    const result = parseSequenceInput('ACDEFGHIKLMNPQRSTVWY');
    expect(result.format).toBe('raw');
    expect(result.sequence).toBe('ACDEFGHIKLMNPQRSTVWY');
  });

  it('uppercases raw input', () => {
    const result = parseSequenceInput('acdefghiklmnpqrstvwy');
    expect(result.sequence).toBe('ACDEFGHIKLMNPQRSTVWY');
  });

  it('parses FASTA format with header', () => {
    const fasta = '>test_protein\nACDEFGHIKL\nMNPQRSTVWY';
    const result = parseSequenceInput(fasta);
    expect(result.format).toBe('fasta');
    expect(result.sequence).toBe('ACDEFGHIKLMNPQRSTVWY');
  });

  it('strips whitespace from raw sequences', () => {
    const result = parseSequenceInput('  ACD EFG  ');
    expect(result.sequence).toBe('ACDEFG');
  });
});

describe('formatResultMetadata', () => {
  it('formats metadata from a complete result', () => {
    const result: AlphaFoldResult = {
      pdbContent: 'ATOM...',
      filename: 'test.pdb',
      sequence: 'ACDEFGHIKLMNPQRSTVWY',
      parameters: getDefaultParameters(),
      metadata: {
        sequence_length: 20,
        job_id: 'job-123',
        processing_time: '5 minutes',
        confidence_scores: '90.5',
      },
    };
    const lines = formatResultMetadata(result);
    expect(lines.some((l) => l.includes('20 residues'))).toBe(true);
    expect(lines.some((l) => l.includes('mmseqs2'))).toBe(true);
    expect(lines.some((l) => l.includes('5 minutes'))).toBe(true);
    expect(lines.some((l) => l.includes('90.5'))).toBe(true);
  });

  it('returns empty array when no metadata is present', () => {
    const result: AlphaFoldResult = {
      pdbContent: '',
      filename: 'test.pdb',
      sequence: 'A',
      parameters: getDefaultParameters(),
    };
    expect(formatResultMetadata(result)).toHaveLength(0);
  });

  it('includes energy minimization info when relax is enabled', () => {
    const result: AlphaFoldResult = {
      pdbContent: '',
      filename: 'test.pdb',
      sequence: 'A',
      parameters: { ...getDefaultParameters(), relax_prediction: true },
      metadata: {
        sequence_length: 1,
        job_id: 'j',
        processing_time: '1m',
        confidence_scores: '0',
      },
    };
    const lines = formatResultMetadata(result);
    expect(lines.some((l) => l.includes('Energy minimization'))).toBe(true);
  });
});
