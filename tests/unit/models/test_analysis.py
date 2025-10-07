"""Tests for analysis models."""

from datetime import datetime
from pathlib import Path

import pytest
from patchsmith.models.analysis import AnalysisResult, AnalysisStatistics
from patchsmith.models.finding import CWE, Finding, Severity


class TestAnalysisStatistics:
    """Tests for AnalysisStatistics model."""

    def test_create_empty_statistics(self) -> None:
        """Test creating empty statistics."""
        stats = AnalysisStatistics()

        assert stats.total_findings == 0
        assert stats.by_severity == {}
        assert stats.by_language == {}
        assert stats.by_cwe == {}
        assert stats.false_positives_filtered == 0
        assert stats.duration_seconds is None

    def test_create_statistics_with_data(self) -> None:
        """Test creating statistics with data."""
        stats = AnalysisStatistics(
            total_findings=10,
            by_severity={Severity.HIGH: 3, Severity.MEDIUM: 7},
            by_language={"python": 8, "javascript": 2},
            by_cwe={"CWE-89": 5, "CWE-79": 5},
            false_positives_filtered=2,
            duration_seconds=45.3,
        )

        assert stats.total_findings == 10
        assert stats.by_severity[Severity.HIGH] == 3
        assert stats.by_language["python"] == 8
        assert stats.by_cwe["CWE-89"] == 5
        assert stats.false_positives_filtered == 2
        assert stats.duration_seconds == 45.3

    def test_get_critical_count(self) -> None:
        """Test getting critical findings count."""
        stats = AnalysisStatistics(
            by_severity={Severity.CRITICAL: 2, Severity.HIGH: 5}
        )

        assert stats.get_critical_count() == 2

    def test_get_critical_count_when_none(self) -> None:
        """Test getting critical count when there are none."""
        stats = AnalysisStatistics(by_severity={Severity.HIGH: 5})

        assert stats.get_critical_count() == 0

    def test_get_high_count(self) -> None:
        """Test getting high severity findings count."""
        stats = AnalysisStatistics(
            by_severity={Severity.CRITICAL: 2, Severity.HIGH: 5}
        )

        assert stats.get_high_count() == 5

    def test_get_actionable_count(self) -> None:
        """Test getting actionable findings count (critical + high)."""
        stats = AnalysisStatistics(
            by_severity={
                Severity.CRITICAL: 2,
                Severity.HIGH: 5,
                Severity.MEDIUM: 10,
            }
        )

        assert stats.get_actionable_count() == 7  # 2 + 5


class TestAnalysisResult:
    """Tests for AnalysisResult model."""

    @pytest.fixture
    def sample_findings(self) -> list[Finding]:
        """Create sample findings for testing."""
        return [
            Finding(
                id="F1",
                rule_id="py/sql-injection",
                severity=Severity.CRITICAL,
                cwe=CWE(id="CWE-89"),
                file_path=Path("src/db.py"),
                start_line=42,
                end_line=45,
                message="SQL injection",
            ),
            Finding(
                id="F2",
                rule_id="py/xss",
                severity=Severity.HIGH,
                cwe=CWE(id="CWE-79"),
                file_path=Path("src/web.py"),
                start_line=100,
                end_line=100,
                message="XSS vulnerability",
            ),
            Finding(
                id="F3",
                rule_id="py/weak-crypto",
                severity=Severity.MEDIUM,
                cwe=CWE(id="CWE-327"),
                file_path=Path("src/crypto.py"),
                start_line=20,
                end_line=22,
                message="Weak cryptography",
            ),
            Finding(
                id="F4",
                rule_id="py/info",
                severity=Severity.INFO,
                file_path=Path("src/db.py"),
                start_line=10,
                end_line=10,
                message="Info finding",
            ),
        ]

    def test_create_analysis_result(self, sample_findings: list[Finding]) -> None:
        """Test creating analysis result."""
        result = AnalysisResult(
            project_name="test-project",
            findings=sample_findings,
            languages_analyzed=["python"],
        )

        assert result.project_name == "test-project"
        assert len(result.findings) == 4
        assert result.languages_analyzed == ["python"]
        assert isinstance(result.timestamp, datetime)
        assert isinstance(result.statistics, AnalysisStatistics)

    def test_filter_by_severity(self, sample_findings: list[Finding]) -> None:
        """Test filtering findings by minimum severity."""
        result = AnalysisResult(
            project_name="test",
            findings=sample_findings,
        )

        # Filter for HIGH and above
        high_and_above = result.filter_by_severity(Severity.HIGH)
        assert len(high_and_above) == 2  # CRITICAL and HIGH

        # Filter for MEDIUM and above
        medium_and_above = result.filter_by_severity(Severity.MEDIUM)
        assert len(medium_and_above) == 3  # CRITICAL, HIGH, MEDIUM

        # Filter for CRITICAL only
        critical = result.filter_by_severity(Severity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].severity == Severity.CRITICAL

    def test_filter_out_false_positives(self) -> None:
        """Test filtering out false positives."""
        from patchsmith.models.finding import FalsePositiveScore

        findings = [
            Finding(
                id="F1",
                rule_id="test",
                severity=Severity.HIGH,
                file_path=Path("test.py"),
                start_line=1,
                end_line=1,
                message="Real issue",
            ),
            Finding(
                id="F2",
                rule_id="test",
                severity=Severity.HIGH,
                file_path=Path("test.py"),
                start_line=10,
                end_line=10,
                message="False positive",
                false_positive_score=FalsePositiveScore(
                    score=0.9,
                    reasoning="Input is validated",
                    is_false_positive=True,
                ),
            ),
        ]

        result = AnalysisResult(project_name="test", findings=findings)
        real_findings = result.filter_out_false_positives()

        assert len(real_findings) == 1
        assert real_findings[0].id == "F1"

    def test_get_by_severity(self, sample_findings: list[Finding]) -> None:
        """Test getting findings by specific severity."""
        result = AnalysisResult(project_name="test", findings=sample_findings)

        high = result.get_by_severity(Severity.HIGH)
        assert len(high) == 1
        assert high[0].severity == Severity.HIGH

        critical = result.get_by_severity(Severity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].severity == Severity.CRITICAL

        low = result.get_by_severity(Severity.LOW)
        assert len(low) == 0

    def test_get_by_file(self, sample_findings: list[Finding]) -> None:
        """Test getting findings by file."""
        result = AnalysisResult(project_name="test", findings=sample_findings)

        db_findings = result.get_by_file("src/db.py")
        assert len(db_findings) == 2  # F1 and F4

        web_findings = result.get_by_file("src/web.py")
        assert len(web_findings) == 1

        nonexistent = result.get_by_file("src/nonexistent.py")
        assert len(nonexistent) == 0

    def test_sort_by_severity(self, sample_findings: list[Finding]) -> None:
        """Test sorting findings by severity."""
        result = AnalysisResult(project_name="test", findings=sample_findings)

        sorted_findings = result.sort_by_severity()

        # Should be ordered: CRITICAL, HIGH, MEDIUM, INFO
        assert sorted_findings[0].severity == Severity.CRITICAL
        assert sorted_findings[1].severity == Severity.HIGH
        assert sorted_findings[2].severity == Severity.MEDIUM
        assert sorted_findings[3].severity == Severity.INFO

    def test_compute_statistics(self, sample_findings: list[Finding]) -> None:
        """Test computing statistics from findings."""
        result = AnalysisResult(project_name="test", findings=sample_findings)

        result.compute_statistics()

        assert result.statistics.total_findings == 4
        assert result.statistics.by_severity[Severity.CRITICAL] == 1
        assert result.statistics.by_severity[Severity.HIGH] == 1
        assert result.statistics.by_severity[Severity.MEDIUM] == 1
        assert result.statistics.by_severity[Severity.INFO] == 1
        assert result.statistics.by_cwe["CWE-89"] == 1
        assert result.statistics.by_cwe["CWE-79"] == 1
        assert result.statistics.by_cwe["CWE-327"] == 1
        assert result.statistics.false_positives_filtered == 0

    def test_compute_statistics_with_false_positives(self) -> None:
        """Test computing statistics with false positives."""
        from patchsmith.models.finding import FalsePositiveScore

        findings = [
            Finding(
                id="F1",
                rule_id="test",
                severity=Severity.HIGH,
                file_path=Path("test.py"),
                start_line=1,
                end_line=1,
                message="Real issue",
            ),
            Finding(
                id="F2",
                rule_id="test",
                severity=Severity.HIGH,
                file_path=Path("test.py"),
                start_line=10,
                end_line=10,
                message="False positive",
                false_positive_score=FalsePositiveScore(
                    score=0.9,
                    reasoning="Validated",
                    is_false_positive=True,
                ),
            ),
        ]

        result = AnalysisResult(project_name="test", findings=findings)
        result.compute_statistics()

        assert result.statistics.total_findings == 2
        assert result.statistics.false_positives_filtered == 1

    def test_compute_statistics_groups_by_cwe(self) -> None:
        """Test statistics correctly groups multiple findings by CWE."""
        findings = [
            Finding(
                id="F1",
                rule_id="test",
                severity=Severity.HIGH,
                cwe=CWE(id="CWE-89"),
                file_path=Path("test1.py"),
                start_line=1,
                end_line=1,
                message="SQL injection 1",
            ),
            Finding(
                id="F2",
                rule_id="test",
                severity=Severity.HIGH,
                cwe=CWE(id="CWE-89"),
                file_path=Path("test2.py"),
                start_line=1,
                end_line=1,
                message="SQL injection 2",
            ),
            Finding(
                id="F3",
                rule_id="test",
                severity=Severity.MEDIUM,
                cwe=CWE(id="CWE-79"),
                file_path=Path("test3.py"),
                start_line=1,
                end_line=1,
                message="XSS",
            ),
        ]

        result = AnalysisResult(project_name="test", findings=findings)
        result.compute_statistics()

        assert result.statistics.by_cwe["CWE-89"] == 2
        assert result.statistics.by_cwe["CWE-79"] == 1

    def test_empty_analysis_result(self) -> None:
        """Test analysis result with no findings."""
        result = AnalysisResult(project_name="test")

        assert len(result.findings) == 0
        result.compute_statistics()
        assert result.statistics.total_findings == 0
        assert result.statistics.get_actionable_count() == 0
