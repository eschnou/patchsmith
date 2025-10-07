"""Tests for finding models."""

from pathlib import Path

import pytest
from patchsmith.models.finding import CWE, FalsePositiveScore, Finding, Severity


class TestSeverity:
    """Tests for Severity enum."""

    def test_from_string(self) -> None:
        """Test creating Severity from string."""
        assert Severity.from_string("critical") == Severity.CRITICAL
        assert Severity.from_string("CRITICAL") == Severity.CRITICAL
        assert Severity.from_string("High") == Severity.HIGH

    def test_from_string_invalid(self) -> None:
        """Test invalid severity string raises error."""
        with pytest.raises(ValueError, match="Invalid severity"):
            Severity.from_string("invalid")


class TestCWE:
    """Tests for CWE model."""

    def test_create_cwe(self) -> None:
        """Test creating CWE."""
        cwe = CWE(id="CWE-89", name="SQL Injection")
        assert cwe.id == "CWE-89"
        assert cwe.name == "SQL Injection"

    def test_cwe_id_normalization(self) -> None:
        """Test CWE ID is normalized."""
        cwe = CWE(id="89")
        assert cwe.id == "CWE-89"

        cwe2 = CWE(id="cwe-89")
        assert cwe2.id == "CWE-89"


class TestFalsePositiveScore:
    """Tests for FalsePositiveScore model."""

    def test_create_false_positive_score(self) -> None:
        """Test creating false positive score."""
        fps = FalsePositiveScore(score=0.8, reasoning="Input is validated", is_false_positive=True)

        assert fps.score == 0.8
        assert fps.is_false_positive is True

    def test_is_false_positive_derived_from_score(self) -> None:
        """Test is_false_positive is derived from score if not set."""
        fps_high = FalsePositiveScore(score=0.9, reasoning="Test", is_false_positive=True)
        assert fps_high.is_false_positive is True

        fps_low = FalsePositiveScore(score=0.3, reasoning="Test", is_false_positive=False)
        assert fps_low.is_false_positive is False


class TestFinding:
    """Tests for Finding model."""

    def test_create_finding(self) -> None:
        """Test creating a basic finding."""
        finding = Finding(
            id="FINDING-001",
            rule_id="py/sql-injection",
            severity=Severity.CRITICAL,
            file_path=Path("src/main.py"),
            start_line=42,
            end_line=45,
            message="SQL injection vulnerability",
        )

        assert finding.id == "FINDING-001"
        assert finding.severity == Severity.CRITICAL
        assert finding.start_line == 42

    def test_finding_with_cwe(self) -> None:
        """Test finding with CWE."""
        finding = Finding(
            id="FINDING-001",
            rule_id="py/sql-injection",
            severity=Severity.HIGH,
            cwe=CWE(id="CWE-89"),
            file_path=Path("src/main.py"),
            start_line=42,
            end_line=42,
            message="SQL injection",
        )

        assert finding.cwe is not None
        assert finding.cwe.id == "CWE-89"

    def test_location_property(self) -> None:
        """Test location property formatting."""
        # Single line
        finding1 = Finding(
            id="F1",
            rule_id="test",
            severity=Severity.LOW,
            file_path=Path("test.py"),
            start_line=10,
            end_line=10,
            message="test",
        )
        assert finding1.location == "test.py:10"

        # Multi-line
        finding2 = Finding(
            id="F2",
            rule_id="test",
            severity=Severity.LOW,
            file_path=Path("test.py"),
            start_line=10,
            end_line=15,
            message="test",
        )
        assert finding2.location == "test.py:10-15"

    def test_end_line_validation(self) -> None:
        """Test end_line must be >= start_line."""
        with pytest.raises(ValueError, match="end_line must be >= start_line"):
            Finding(
                id="F1",
                rule_id="test",
                severity=Severity.LOW,
                file_path=Path("test.py"),
                start_line=10,
                end_line=5,  # Invalid: before start_line
                message="test",
            )

    def test_is_likely_false_positive(self) -> None:
        """Test false positive detection."""
        # No FP score
        finding1 = Finding(
            id="F1",
            rule_id="test",
            severity=Severity.LOW,
            file_path=Path("test.py"),
            start_line=1,
            end_line=1,
            message="test",
        )
        assert finding1.is_likely_false_positive is False

        # With FP score - likely FP
        finding2 = Finding(
            id="F2",
            rule_id="test",
            severity=Severity.LOW,
            file_path=Path("test.py"),
            start_line=1,
            end_line=1,
            message="test",
            false_positive_score=FalsePositiveScore(
                score=0.9, reasoning="Validated input", is_false_positive=True
            ),
        )
        assert finding2.is_likely_false_positive is True

        # With FP score - not FP
        finding3 = Finding(
            id="F3",
            rule_id="test",
            severity=Severity.LOW,
            file_path=Path("test.py"),
            start_line=1,
            end_line=1,
            message="test",
            false_positive_score=FalsePositiveScore(
                score=0.2, reasoning="Real issue", is_false_positive=False
            ),
        )
        assert finding3.is_likely_false_positive is False

    def test_get_severity_rank(self) -> None:
        """Test severity ranking."""
        critical = Finding(
            id="F1",
            rule_id="test",
            severity=Severity.CRITICAL,
            file_path=Path("test.py"),
            start_line=1,
            end_line=1,
            message="test",
        )
        assert critical.get_severity_rank() == 4

        info = Finding(
            id="F2",
            rule_id="test",
            severity=Severity.INFO,
            file_path=Path("test.py"),
            start_line=1,
            end_line=1,
            message="test",
        )
        assert info.get_severity_rank() == 0

        # Critical should rank higher than info
        assert critical.get_severity_rank() > info.get_severity_rank()
