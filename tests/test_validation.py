"""Test the structure validation engine."""

import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from tools.validation.structure_validator import validate_structure, ValidationReport


# A minimal valid PDB with B-factors (simulated pLDDT)
SAMPLE_PDB = """ATOM      1  N   ALA A   1       1.000   1.000   1.000  1.00 85.00           N
ATOM      2  CA  ALA A   1       2.000   1.000   1.000  1.00 85.00           C
ATOM      3  C   ALA A   1       3.000   1.000   1.000  1.00 85.00           C
ATOM      4  O   ALA A   1       3.000   2.000   1.000  1.00 85.00           O
ATOM      5  N   GLY A   2       4.000   1.000   1.000  1.00 72.00           N
ATOM      6  CA  GLY A   2       5.000   1.000   1.000  1.00 72.00           C
ATOM      7  C   GLY A   2       6.000   1.000   1.000  1.00 72.00           C
ATOM      8  O   GLY A   2       6.000   2.000   1.000  1.00 72.00           O
ATOM      9  N   VAL A   3       7.000   1.000   1.000  1.00 45.00           N
ATOM     10  CA  VAL A   3       8.000   1.000   1.000  1.00 45.00           C
ATOM     11  C   VAL A   3       9.000   1.000   1.000  1.00 45.00           C
ATOM     12  O   VAL A   3       9.000   2.000   1.000  1.00 45.00           O
END
"""


def test_validate_structure_returns_report():
    """validate_structure returns a ValidationReport with grade and metrics."""
    report = validate_structure(SAMPLE_PDB)
    assert isinstance(report, ValidationReport)
    assert report.grade in ("A", "B", "C", "D", "F")
    assert report.total_residues >= 0
    assert report.overall_score >= 0
    print(f"Grade: {report.grade}, Score: {report.overall_score}, Residues: {report.total_residues}")


def test_plddt_values_extracted():
    """pLDDT values are correctly extracted from B-factor column."""
    report = validate_structure(SAMPLE_PDB)
    assert len(report.plddt_per_residue) > 0, "Expected at least one residue in plddt_per_residue"
    values = [r["plddt"] for r in report.plddt_per_residue]
    assert all(0 <= v <= 100 for v in values if v is not None)
    # Verify the specific B-factor values we put in the sample PDB
    assert 85.0 in values, "Expected pLDDT 85.0 from ALA residue"
    assert 72.0 in values, "Expected pLDDT 72.0 from GLY residue"
    assert 45.0 in values, "Expected pLDDT 45.0 from VAL residue"
    print(f"pLDDT values: {values}")


def test_empty_pdb_raises_value_error():
    """Empty PDB content raises ValueError."""
    try:
        validate_structure("")
        assert False, "Expected ValueError for empty PDB content"
    except ValueError as e:
        print(f"Empty PDB correctly raised ValueError: {e}")


def test_whitespace_only_pdb_raises_value_error():
    """Whitespace-only PDB content raises ValueError."""
    try:
        validate_structure("   \n\n  ")
        assert False, "Expected ValueError for whitespace-only PDB content"
    except ValueError as e:
        print(f"Whitespace PDB correctly raised ValueError: {e}")


def test_suggestions_generated():
    """Suggestions are generated as a list of strings based on metrics."""
    report = validate_structure(SAMPLE_PDB)
    assert isinstance(report.suggestions, list)
    assert len(report.suggestions) > 0, "Expected at least one suggestion"
    for s in report.suggestions:
        assert isinstance(s, str), f"Expected suggestion to be a string, got {type(s)}"
        assert len(s) > 0, "Expected non-empty suggestion string"
    print(f"Suggestions ({len(report.suggestions)}): {report.suggestions}")


def test_plddt_statistics():
    """pLDDT mean and median are computed correctly."""
    report = validate_structure(SAMPLE_PDB)
    # Expected: mean of [85, 72, 45] = 67.33, median = 72
    assert abs(report.plddt_mean - 67.33) < 1.0, f"Expected pLDDT mean ~67.33, got {report.plddt_mean}"
    assert abs(report.plddt_median - 72.0) < 0.01, f"Expected pLDDT median 72.0, got {report.plddt_median}"
    # High confidence (>=70): ALA(85) and GLY(72) = 2
    assert report.plddt_high_confidence == 2, f"Expected 2 high-confidence residues, got {report.plddt_high_confidence}"
    # Low confidence (<50): VAL(45) = 1
    assert report.plddt_low_confidence == 1, f"Expected 1 low-confidence residue, got {report.plddt_low_confidence}"
    print(f"pLDDT mean={report.plddt_mean}, median={report.plddt_median}, "
          f"high={report.plddt_high_confidence}, low={report.plddt_low_confidence}")


def test_chain_detection():
    """Chain IDs are correctly extracted from the PDB."""
    report = validate_structure(SAMPLE_PDB)
    assert "A" in report.chains, f"Expected chain 'A' in chains, got {report.chains}"
    assert report.total_residues == 3, f"Expected 3 residues, got {report.total_residues}"
    print(f"Chains: {report.chains}, Total residues: {report.total_residues}")


def test_report_to_dict():
    """ValidationReport.to_dict() returns a serializable dictionary."""
    report = validate_structure(SAMPLE_PDB)
    d = report.to_dict()
    assert isinstance(d, dict)
    assert "grade" in d
    assert "overall_score" in d
    assert "suggestions" in d
    assert "plddt_per_residue" in d
    assert "total_residues" in d
    print(f"to_dict() keys: {sorted(d.keys())}")


def test_overall_score_range():
    """Overall score is between 0 and 100."""
    report = validate_structure(SAMPLE_PDB)
    assert 0 <= report.overall_score <= 100, f"Score {report.overall_score} out of range [0, 100]"
    print(f"Overall score: {report.overall_score}")


if __name__ == "__main__":
    tests = [
        test_validate_structure_returns_report,
        test_plddt_values_extracted,
        test_empty_pdb_raises_value_error,
        test_whitespace_only_pdb_raises_value_error,
        test_suggestions_generated,
        test_plddt_statistics,
        test_chain_detection,
        test_report_to_dict,
        test_overall_score_range,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        name = test_fn.__name__
        try:
            print(f"\n--- {name} ---")
            test_fn()
            print(f"PASSED: {name}")
            passed += 1
        except Exception as e:
            print(f"FAILED: {name} - {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    if failed == 0:
        print("All tests passed!")
    else:
        print("Some tests FAILED!")
        sys.exit(1)
