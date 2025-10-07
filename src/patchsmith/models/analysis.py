"""Analysis result models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from patchsmith.models.finding import Finding, Severity


class AnalysisStatistics(BaseModel):
    """Statistics about analysis results."""

    total_findings: int = Field(default=0, description="Total number of findings")
    by_severity: dict[Severity, int] = Field(
        default_factory=dict, description="Findings grouped by severity"
    )
    by_language: dict[str, int] = Field(
        default_factory=dict, description="Findings grouped by language"
    )
    by_cwe: dict[str, int] = Field(default_factory=dict, description="Findings grouped by CWE")
    false_positives_filtered: int = Field(
        default=0, description="Number of findings marked as false positives"
    )
    duration_seconds: Optional[float] = Field(default=None, description="Analysis duration in seconds")

    def get_critical_count(self) -> int:
        """Get count of critical findings."""
        return self.by_severity.get(Severity.CRITICAL, 0)

    def get_high_count(self) -> int:
        """Get count of high severity findings."""
        return self.by_severity.get(Severity.HIGH, 0)

    def get_actionable_count(self) -> int:
        """Get count of critical and high severity findings."""
        return self.get_critical_count() + self.get_high_count()


class AnalysisResult(BaseModel):
    """Complete analysis result."""

    findings: list[Finding] = Field(default_factory=list, description="All findings")
    statistics: AnalysisStatistics = Field(
        default_factory=lambda: AnalysisStatistics(), description="Analysis statistics"
    )
    timestamp: datetime = Field(default_factory=datetime.now, description="Analysis timestamp")
    project_name: str = Field(..., description="Name of analyzed project")
    languages_analyzed: list[str] = Field(
        default_factory=list, description="Languages that were analyzed"
    )

    def filter_by_severity(self, min_severity: Severity) -> list[Finding]:
        """
        Filter findings by minimum severity level.

        Args:
            min_severity: Minimum severity to include

        Returns:
            Filtered list of findings
        """
        severity_order = [
            Severity.INFO,
            Severity.LOW,
            Severity.MEDIUM,
            Severity.HIGH,
            Severity.CRITICAL,
        ]
        min_rank = severity_order.index(min_severity)

        return [f for f in self.findings if severity_order.index(f.severity) >= min_rank]

    def filter_out_false_positives(self) -> list[Finding]:
        """
        Filter out likely false positives.

        Returns:
            Findings that are not likely false positives
        """
        return [f for f in self.findings if not f.is_likely_false_positive]

    def get_by_severity(self, severity: Severity) -> list[Finding]:
        """
        Get findings of a specific severity.

        Args:
            severity: Severity level to filter by

        Returns:
            Findings with the specified severity
        """
        return [f for f in self.findings if f.severity == severity]

    def get_by_file(self, file_path: str) -> list[Finding]:
        """
        Get all findings in a specific file.

        Args:
            file_path: Path to file

        Returns:
            Findings in the specified file
        """
        return [f for f in self.findings if str(f.file_path) == file_path]

    def sort_by_severity(self) -> list[Finding]:
        """
        Sort findings by severity (most severe first).

        Returns:
            Sorted list of findings
        """
        return sorted(self.findings, key=lambda f: f.get_severity_rank(), reverse=True)

    def compute_statistics(self) -> None:
        """Compute statistics from findings and update the statistics field."""
        stats = AnalysisStatistics(total_findings=len(self.findings))

        # Count by severity
        for severity in Severity:
            count = len([f for f in self.findings if f.severity == severity])
            if count > 0:
                stats.by_severity[severity] = count

        # Count by CWE
        for finding in self.findings:
            if finding.cwe:
                cwe_id = finding.cwe.id
                stats.by_cwe[cwe_id] = stats.by_cwe.get(cwe_id, 0) + 1

        # Count false positives
        stats.false_positives_filtered = len(
            [f for f in self.findings if f.is_likely_false_positive]
        )

        self.statistics = stats
