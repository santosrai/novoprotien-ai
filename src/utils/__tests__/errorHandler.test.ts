import { describe, it, expect } from 'vitest';
import {
  AlphaFoldErrorHandler,
  RFdiffusionErrorHandler,
  OpenFold2ErrorHandler,
  ErrorCategory,
  ErrorSeverity,
} from '../errorHandler';

describe('AlphaFoldErrorHandler', () => {
  describe('createError', () => {
    it('creates an error from a known error code', () => {
      const error = AlphaFoldErrorHandler.createError('SEQUENCE_EMPTY');
      expect(error.code).toBe('SEQUENCE_EMPTY');
      expect(error.category).toBe(ErrorCategory.VALIDATION);
      expect(error.severity).toBe(ErrorSeverity.MEDIUM);
      expect(error.userMessage).toBe('No protein sequence provided');
      expect(error.suggestions.length).toBeGreaterThan(0);
      expect(error.timestamp).toBeInstanceOf(Date);
    });

    it('returns a fallback error for unknown error codes', () => {
      const error = AlphaFoldErrorHandler.createError('NONEXISTENT_CODE');
      expect(error.code).toBe('UNKNOWN_ERROR');
      expect(error.category).toBe(ErrorCategory.SYSTEM);
      expect(error.severity).toBe(ErrorSeverity.HIGH);
    });

    it('injects context into error messages', () => {
      const error = AlphaFoldErrorHandler.createError('SEQUENCE_TOO_SHORT', {
        sequenceLength: 10,
      });
      expect(error.technicalMessage).toContain('10');
    });

    it('includes requestId when provided', () => {
      const error = AlphaFoldErrorHandler.createError(
        'SEQUENCE_EMPTY',
        {},
        undefined,
        undefined,
        'req-123'
      );
      expect(error.requestId).toBe('req-123');
    });
  });

  describe('handleSequenceValidation', () => {
    it('returns null for a valid sequence', () => {
      const seq = 'ACDEFGHIKLMNPQRSTVWY'.repeat(2); // 40 chars, all valid
      expect(AlphaFoldErrorHandler.handleSequenceValidation(seq)).toBeNull();
    });

    it('detects empty sequences', () => {
      const error = AlphaFoldErrorHandler.handleSequenceValidation('');
      expect(error).not.toBeNull();
      expect(error!.code).toBe('SEQUENCE_EMPTY');
    });

    it('detects whitespace-only sequences', () => {
      const error = AlphaFoldErrorHandler.handleSequenceValidation('   \n\t  ');
      expect(error).not.toBeNull();
      expect(error!.code).toBe('SEQUENCE_EMPTY');
    });

    it('detects sequences that are too short', () => {
      const error = AlphaFoldErrorHandler.handleSequenceValidation('ACDEFG');
      expect(error).not.toBeNull();
      expect(error!.code).toBe('SEQUENCE_TOO_SHORT');
    });

    it('detects sequences that are too long', () => {
      const longSeq = 'A'.repeat(2001);
      const error = AlphaFoldErrorHandler.handleSequenceValidation(longSeq);
      expect(error).not.toBeNull();
      expect(error!.code).toBe('SEQUENCE_TOO_LONG');
    });

    it('detects invalid amino acid characters', () => {
      const seq = 'ACDEFGHIKLMNPQRSTVWYX'.repeat(2); // X is invalid, 42 chars
      const error = AlphaFoldErrorHandler.handleSequenceValidation(seq);
      expect(error).not.toBeNull();
      expect(error!.code).toBe('INVALID_AMINO_ACIDS');
      expect(error!.context.invalidCharacters).toContain('X');
    });

    it('strips whitespace before validation', () => {
      const seq = 'A C D E F G H I K L M N P Q R S T V W Y'; // valid once cleaned
      expect(AlphaFoldErrorHandler.handleSequenceValidation(seq)).toBeNull();
    });
  });

  describe('handleAPIError', () => {
    it('handles 401 unauthorized', () => {
      const error = AlphaFoldErrorHandler.handleAPIError({
        response: { status: 401 },
        config: { url: '/api/fold' },
        message: 'Unauthorized',
      });
      expect(error.code).toBe('API_KEY_INVALID');
      expect(error.category).toBe(ErrorCategory.AUTH);
    });

    it('handles 429 rate limit', () => {
      const error = AlphaFoldErrorHandler.handleAPIError({
        response: { status: 429, headers: { 'retry-after': '60' } },
        message: 'Rate limited',
      });
      expect(error.code).toBe('QUOTA_EXCEEDED');
      expect(error.category).toBe(ErrorCategory.QUOTA);
    });

    it('handles connection refused', () => {
      const error = AlphaFoldErrorHandler.handleAPIError({
        code: 'ECONNREFUSED',
        message: 'Connection refused',
      });
      expect(error.code).toBe('API_UNAVAILABLE');
      expect(error.category).toBe(ErrorCategory.NETWORK);
    });

    it('handles timeout', () => {
      const error = AlphaFoldErrorHandler.handleAPIError({
        code: 'ETIMEDOUT',
        message: 'Timed out',
      });
      expect(error.code).toBe('TIMEOUT');
      expect(error.category).toBe(ErrorCategory.TIMEOUT);
    });

    it('falls back to UNKNOWN_ERROR for generic errors', () => {
      const error = AlphaFoldErrorHandler.handleAPIError({
        response: { status: 500 },
        message: 'Server error',
      });
      expect(error.code).toBe('UNKNOWN_ERROR');
    });
  });

  describe('handlePDBError', () => {
    it('returns PDB_NOT_FOUND when no chain is specified', () => {
      const error = AlphaFoldErrorHandler.handlePDBError('1XYZ');
      expect(error.code).toBe('PDB_NOT_FOUND');
      expect(error.context.pdbId).toBe('1XYZ');
    });

    it('returns CHAIN_NOT_FOUND when a chain is specified', () => {
      const error = AlphaFoldErrorHandler.handlePDBError('1XYZ', 'B');
      expect(error.code).toBe('CHAIN_NOT_FOUND');
      expect(error.context.chain).toBe('B');
    });
  });

  describe('getSeverityColor', () => {
    it('returns correct color class for each severity', () => {
      expect(AlphaFoldErrorHandler.getSeverityColor(ErrorSeverity.LOW)).toBe('text-yellow-700');
      expect(AlphaFoldErrorHandler.getSeverityColor(ErrorSeverity.MEDIUM)).toBe('text-orange-700');
      expect(AlphaFoldErrorHandler.getSeverityColor(ErrorSeverity.HIGH)).toBe('text-red-700');
      expect(AlphaFoldErrorHandler.getSeverityColor(ErrorSeverity.CRITICAL)).toBe('text-red-900');
    });

    it('returns fallback color for unknown severity', () => {
      expect(AlphaFoldErrorHandler.getSeverityColor('unknown' as ErrorSeverity)).toBe('text-gray-700');
    });
  });
});

describe('RFdiffusionErrorHandler', () => {
  describe('createError', () => {
    it('creates errors for known RFdiffusion error codes', () => {
      const error = RFdiffusionErrorHandler.createError('CONTIGS_EMPTY');
      expect(error.code).toBe('CONTIGS_EMPTY');
      expect(error.category).toBe(ErrorCategory.VALIDATION);
    });

    it('falls back for unknown codes', () => {
      const error = RFdiffusionErrorHandler.createError('NONEXISTENT');
      expect(error.code).toBe('UNKNOWN_ERROR');
    });
  });

  describe('handleError', () => {
    it('categorizes network errors', () => {
      const error = RFdiffusionErrorHandler.handleError({ message: 'network error' });
      expect(error.technicalMessage).toContain('network error');
    });

    it('categorizes timeout errors', () => {
      const error = RFdiffusionErrorHandler.handleError({ message: 'timeout occurred' });
      expect(error.code).toBe('DESIGN_TIMEOUT');
    });

    it('categorizes contigs errors', () => {
      const error = RFdiffusionErrorHandler.handleError({ message: 'invalid contigs spec' });
      expect(error.code).toBe('CONTIGS_INVALID');
    });

    it('categorizes auth errors', () => {
      const error = RFdiffusionErrorHandler.handleError({ message: 'unauthorized access' });
      expect(error.code).toBe('RFDIFFUSION_API_NOT_CONFIGURED');
    });
  });
});

describe('OpenFold2ErrorHandler', () => {
  describe('handleSequenceValidation', () => {
    it('returns null for a valid sequence', () => {
      const seq = 'ACDEFGHIKLMNPQRSTVWY'.repeat(2);
      expect(OpenFold2ErrorHandler.handleSequenceValidation(seq)).toBeNull();
    });

    it('detects empty sequences', () => {
      const error = OpenFold2ErrorHandler.handleSequenceValidation('');
      expect(error).not.toBeNull();
      expect(error!.code).toBe('SEQUENCE_EMPTY');
    });

    it('detects sequences too short', () => {
      const error = OpenFold2ErrorHandler.handleSequenceValidation('ACDEFG');
      expect(error).not.toBeNull();
      expect(error!.code).toBe('SEQUENCE_TOO_SHORT');
    });

    it('detects sequences exceeding OpenFold2 limit (1000 residues)', () => {
      const longSeq = 'A'.repeat(1001);
      const error = OpenFold2ErrorHandler.handleSequenceValidation(longSeq);
      expect(error).not.toBeNull();
      expect(error!.code).toBe('SEQUENCE_TOO_LONG');
    });

    it('detects invalid amino acids', () => {
      const seq = 'ACDEFGHIKLMNPQRSTVWYZ'.repeat(2);
      const error = OpenFold2ErrorHandler.handleSequenceValidation(seq);
      expect(error).not.toBeNull();
      expect(error!.code).toBe('SEQUENCE_INVALID');
    });
  });

  describe('createError', () => {
    it('creates known OpenFold2 errors', () => {
      const error = OpenFold2ErrorHandler.createError('API_KEY_MISSING');
      expect(error.code).toBe('API_KEY_MISSING');
      expect(error.category).toBe(ErrorCategory.AUTH);
      expect(error.severity).toBe(ErrorSeverity.CRITICAL);
    });
  });
});
