import { describe, it, expect } from 'vitest';
import { validatePDBId, getPDBUrl, resolvePDBFromName } from '../pdbUtils';

describe('validatePDBId', () => {
  it('accepts valid 4-character PDB IDs starting with a digit', () => {
    expect(validatePDBId('1ABC')).toBe(true);
    expect(validatePDBId('2XYZ')).toBe(true);
    expect(validatePDBId('9ZZZ')).toBe(true);
    expect(validatePDBId('1hho')).toBe(true);
  });

  it('rejects IDs that do not start with a digit', () => {
    expect(validatePDBId('ABCD')).toBe(false);
    expect(validatePDBId('xyzw')).toBe(false);
  });

  it('rejects IDs that are not exactly 4 characters', () => {
    expect(validatePDBId('1AB')).toBe(false);
    expect(validatePDBId('1ABCD')).toBe(false);
    expect(validatePDBId('')).toBe(false);
  });

  it('rejects IDs with special characters', () => {
    expect(validatePDBId('1A-C')).toBe(false);
    expect(validatePDBId('1A C')).toBe(false);
  });
});

describe('getPDBUrl', () => {
  it('returns the correct RCSB download URL', () => {
    expect(getPDBUrl('1HHO')).toBe('https://files.rcsb.org/view/1HHO.pdb');
  });

  it('uppercases the PDB ID in the URL', () => {
    expect(getPDBUrl('1hho')).toBe('https://files.rcsb.org/view/1HHO.pdb');
  });
});

describe('resolvePDBFromName', () => {
  it('resolves common protein names to known PDB IDs', async () => {
    expect(await resolvePDBFromName('insulin')).toBe('1ZNI');
    expect(await resolvePDBFromName('hemoglobin')).toBe('1HHO');
    expect(await resolvePDBFromName('lysozyme')).toBe('6LYZ');
  });

  it('is case-insensitive for common protein names', async () => {
    expect(await resolvePDBFromName('INSULIN')).toBe('1ZNI');
    expect(await resolvePDBFromName('Hemoglobin')).toBe('1HHO');
  });

  it('returns a 4-character PDB code as-is (uppercased)', async () => {
    expect(await resolvePDBFromName('1abc')).toBe('1ABC');
    expect(await resolvePDBFromName('2XYZ')).toBe('2XYZ');
  });
});
