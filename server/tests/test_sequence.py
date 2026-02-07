"""Tests for server.domain.protein.sequence module."""
import pytest
from server.domain.protein.sequence import SequenceExtractor


@pytest.fixture
def extractor():
    return SequenceExtractor()


# ---------------------------------------------------------------------------
# _extract_sequences_from_pdb_content
# ---------------------------------------------------------------------------

class TestExtractSequencesFromPDBContent:
    def test_extracts_single_chain(self, extractor):
        pdb_content = (
            "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00           C\n"
            "ATOM      2  CA  GLY A   2       4.000   5.000   6.000  1.00  0.00           C\n"
            "ATOM      3  CA  VAL A   3       7.000   8.000   9.000  1.00  0.00           C\n"
        )
        result = extractor._extract_sequences_from_pdb_content(pdb_content)
        assert result == {"A": "AGV"}

    def test_extracts_multiple_chains(self, extractor):
        pdb_content = (
            "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00           C\n"
            "ATOM      2  CA  GLY A   2       4.000   5.000   6.000  1.00  0.00           C\n"
            "ATOM      3  CA  LEU B   1       7.000   8.000   9.000  1.00  0.00           C\n"
            "ATOM      4  CA  MET B   2      10.000  11.000  12.000  1.00  0.00           C\n"
        )
        result = extractor._extract_sequences_from_pdb_content(pdb_content)
        assert result == {"A": "AG", "B": "LM"}

    def test_skips_non_ca_atoms(self, extractor):
        pdb_content = (
            "ATOM      1  N   ALA A   1       1.000   2.000   3.000  1.00  0.00           N\n"
            "ATOM      2  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00           C\n"
            "ATOM      3  C   ALA A   1       1.000   2.000   3.000  1.00  0.00           C\n"
        )
        result = extractor._extract_sequences_from_pdb_content(pdb_content)
        assert result == {"A": "A"}

    def test_skips_non_standard_residues(self, extractor):
        pdb_content = (
            "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00           C\n"
            "ATOM      2  CA  UNK A   2       4.000   5.000   6.000  1.00  0.00           C\n"
            "ATOM      3  CA  GLY A   3       7.000   8.000   9.000  1.00  0.00           C\n"
        )
        result = extractor._extract_sequences_from_pdb_content(pdb_content)
        assert result == {"A": "AG"}

    def test_handles_duplicate_residue_numbers(self, extractor):
        pdb_content = (
            "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00           C\n"
            "ATOM      2  CA  ALA A   1       1.100   2.100   3.100  1.00  0.00           C\n"
            "ATOM      3  CA  GLY A   2       4.000   5.000   6.000  1.00  0.00           C\n"
        )
        result = extractor._extract_sequences_from_pdb_content(pdb_content)
        assert result == {"A": "AG"}

    def test_empty_content_returns_empty_dict(self, extractor):
        assert extractor._extract_sequences_from_pdb_content("") == {}

    def test_ignores_hetatm_lines(self, extractor):
        pdb_content = (
            "HETATM    1  CA  HOH A   1       1.000   2.000   3.000  1.00  0.00           O\n"
            "ATOM      2  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00           C\n"
        )
        result = extractor._extract_sequences_from_pdb_content(pdb_content)
        assert result == {"A": "A"}


# ---------------------------------------------------------------------------
# extract_from_fasta
# ---------------------------------------------------------------------------

class TestExtractFromFasta:
    def test_parses_single_sequence(self, extractor):
        fasta = ">seq1\nACDEFGHIKL\nMNPQRSTVWY"
        result = extractor.extract_from_fasta(fasta)
        assert result == {"seq1": "ACDEFGHIKLMNPQRSTVWY"}

    def test_parses_multiple_sequences(self, extractor):
        fasta = ">seq1\nACDEF\n>seq2\nGHIKL"
        result = extractor.extract_from_fasta(fasta)
        assert result == {"seq1": "ACDEF", "seq2": "GHIKL"}

    def test_handles_empty_input(self, extractor):
        assert extractor.extract_from_fasta("") == {}

    def test_handles_blank_lines(self, extractor):
        fasta = ">seq1\n\nACDEF\n\nGHIKL\n"
        result = extractor.extract_from_fasta(fasta)
        assert result == {"seq1": "ACDEFGHIKL"}

    def test_uppercases_sequence(self, extractor):
        fasta = ">seq1\nacdefghikl"
        result = extractor.extract_from_fasta(fasta)
        assert result == {"seq1": "ACDEFGHIKL"}


# ---------------------------------------------------------------------------
# extract_subsequence
# ---------------------------------------------------------------------------

class TestExtractSubsequence:
    def test_extracts_correct_subsequence(self, extractor):
        seq = "ACDEFGHIKLMNPQRSTVWY"
        assert extractor.extract_subsequence(seq, 1, 5) == "ACDEF"

    def test_extracts_single_residue(self, extractor):
        seq = "ACDEFGHIKLMNPQRSTVWY"
        assert extractor.extract_subsequence(seq, 3, 3) == "D"

    def test_extracts_full_sequence(self, extractor):
        seq = "ACDEF"
        assert extractor.extract_subsequence(seq, 1, 5) == "ACDEF"

    def test_raises_on_start_less_than_1(self, extractor):
        with pytest.raises(ValueError, match="Start position must be >= 1"):
            extractor.extract_subsequence("ACDEF", 0, 3)

    def test_raises_on_end_exceeds_length(self, extractor):
        with pytest.raises(ValueError, match="exceeds sequence length"):
            extractor.extract_subsequence("ACDEF", 1, 10)

    def test_raises_on_start_greater_than_end(self, extractor):
        with pytest.raises(ValueError, match="Start position must be <= end"):
            extractor.extract_subsequence("ACDEF", 4, 2)


# ---------------------------------------------------------------------------
# validate_sequence
# ---------------------------------------------------------------------------

class TestValidateSequence:
    def test_valid_sequence(self, extractor):
        is_valid, errors = extractor.validate_sequence("ACDEFGHIKLMNPQRSTVWY" * 2)
        assert is_valid is True
        assert errors == []

    def test_empty_sequence(self, extractor):
        is_valid, errors = extractor.validate_sequence("")
        assert is_valid is False
        assert any("empty" in e.lower() for e in errors)

    def test_too_short(self, extractor):
        is_valid, errors = extractor.validate_sequence("ACDEF")
        assert is_valid is False
        assert any("short" in e.lower() for e in errors)

    def test_too_long(self, extractor):
        is_valid, errors = extractor.validate_sequence("A" * 2001)
        assert is_valid is False
        assert any("long" in e.lower() for e in errors)

    def test_invalid_characters(self, extractor):
        is_valid, errors = extractor.validate_sequence("ACDEFX" * 10)
        assert is_valid is False
        assert any("Invalid" in e for e in errors)

    def test_strips_whitespace(self, extractor):
        # 20 valid chars with spaces
        seq = "A C D E F G H I K L M N P Q R S T V W Y"
        is_valid, errors = extractor.validate_sequence(seq)
        assert is_valid is True


# ---------------------------------------------------------------------------
# parse_sequence_request
# ---------------------------------------------------------------------------

class TestParseSequenceRequest:
    def test_parses_pdb_id_with_prefix(self, extractor):
        result = extractor.parse_sequence_request("fold PDB:1HHO")
        assert result["type"] == "pdb"
        assert result["pdb_id"] == "1HHO"

    def test_parses_bare_pdb_id(self, extractor):
        result = extractor.parse_sequence_request("fold 1TUP")
        assert result["type"] == "pdb"
        assert result["pdb_id"] == "1TUP"

    def test_parses_chain(self, extractor):
        result = extractor.parse_sequence_request("fold chain A from PDB:1HHO")
        assert result["chain"] == "A"
        assert result["pdb_id"] == "1HHO"

    def test_parses_residue_range(self, extractor):
        result = extractor.parse_sequence_request("fold residues 50-100 from PDB:1HHO")
        assert result["start"] == 50
        assert result["end"] == 100

    def test_detects_direct_sequence(self, extractor):
        long_seq = "ACDEFGHIKLMNPQRSTVWY"
        result = extractor.parse_sequence_request(f"fold {long_seq}")
        assert result["type"] == "sequence"
        assert result["sequence"] == long_seq


# ---------------------------------------------------------------------------
# get_sequence_info
# ---------------------------------------------------------------------------

class TestGetSequenceInfo:
    def test_returns_correct_length(self, extractor):
        info = extractor.get_sequence_info("ACDEFGHIKL")
        assert info["length"] == 10

    def test_counts_amino_acids(self, extractor):
        info = extractor.get_sequence_info("AAACCC")
        assert info["amino_acid_counts"]["A"] == 3
        assert info["amino_acid_counts"]["C"] == 3

    def test_calculates_molecular_weight(self, extractor):
        info = extractor.get_sequence_info("A")
        # Single alanine: weight ~89.1 (no water subtraction for single AA)
        assert info["molecular_weight"] > 0

    def test_strips_whitespace(self, extractor):
        info = extractor.get_sequence_info("A C D")
        assert info["length"] == 3
        assert info["sequence"] == "ACD"
