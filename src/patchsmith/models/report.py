"""Report data models for structured security reports."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ExecutiveSummary(BaseModel):
    """Executive summary section of the report."""

    overall_assessment: str = Field(
        ..., description="High-level assessment of security posture (2-3 paragraphs)"
    )
    critical_findings_count: int = Field(..., description="Number of critical findings")
    high_findings_count: int = Field(..., description="Number of high severity findings")
    key_risks: list[str] = Field(
        ..., description="List of 3-5 key risk areas or vulnerability types"
    )
    immediate_actions: list[str] = Field(
        ..., description="List of 2-4 immediate action items for critical issues"
    )


class StatisticsOverview(BaseModel):
    """Statistics overview section of the report."""

    total_findings: int = Field(..., description="Total number of findings")
    critical_count: int = Field(default=0, description="Critical severity count")
    high_count: int = Field(default=0, description="High severity count")
    medium_count: int = Field(default=0, description="Medium severity count")
    low_count: int = Field(default=0, description="Low severity count")
    info_count: int = Field(default=0, description="Info severity count")
    false_positives_filtered: int = Field(
        default=0, description="Number of findings marked as false positives"
    )
    most_common_cwes: list[tuple[str, int]] = Field(
        default_factory=list, description="List of (CWE, count) tuples for top CWEs"
    )

    @field_validator("most_common_cwes", mode="before")
    @classmethod
    def convert_cwes_to_tuples(cls, v: Any) -> list[tuple[str, int]]:
        """Convert various CWE formats to list of tuples.

        Accepts:
        - [["CWE-89", 5], ["CWE-79", 3]] (lists)
        - [("CWE-89", 5), ("CWE-79", 3)] (tuples)
        - [{"cwe": "CWE-89", "count": 5}] (dicts)
        """
        if not isinstance(v, list):
            return []

        result = []
        for item in v:
            if isinstance(item, list | tuple) and len(item) >= 2:
                # Convert list/tuple to tuple
                result.append((str(item[0]), int(item[1])))
            elif isinstance(item, dict):
                # Handle dict format
                cwe = item.get("cwe") or item.get("name") or item.get("id", "Unknown")
                count = item.get("count") or item.get("occurrences", 0)
                result.append((str(cwe), int(count)))

        return result


class FindingPriority(BaseModel):
    """Prioritized finding with context for the report."""

    finding_id: str = Field(..., description="Finding identifier")
    title: str = Field(..., description="Short title/summary of the finding")
    severity: str = Field(..., description="Severity level (critical, high, medium, low)")
    location: str = Field(..., description="File path and line number")
    description: str = Field(..., description="Brief description of the vulnerability")
    priority_score: float = Field(
        ..., description="Priority score (0.0-1.0)", ge=0.0, le=1.0
    )
    reasoning: str = Field(..., description="Why this was prioritized")
    cwe: str | None = Field(None, description="CWE identifier if available")

    # Detailed analysis fields (if available)
    is_false_positive: bool = Field(default=False, description="True if false positive")
    attack_scenario: str | None = Field(
        None, description="How this could be exploited"
    )
    risk_type: str | None = Field(None, description="Risk classification type")
    exploitability_score: float | None = Field(
        None, description="Exploitability score (0.0-1.0)", ge=0.0, le=1.0
    )
    impact_description: str | None = Field(None, description="Impact if exploited")
    remediation_priority: str | None = Field(
        None, description="Remediation priority (immediate, high, medium, low)"
    )


class RecommendationItem(BaseModel):
    """Actionable recommendation for the report."""

    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed recommendation description")
    priority: str = Field(
        ..., description="Priority level (immediate, high, medium, low)"
    )
    category: str = Field(
        ..., description="Category (remediation, process, tooling, training, etc.)"
    )
    affected_findings: list[str] = Field(
        default_factory=list, description="List of finding IDs this addresses"
    )


class SecurityReportData(BaseModel):
    """Structured security report data.

    This model contains all report content as structured data,
    which can then be formatted into markdown, HTML, or other formats.
    """

    # Metadata
    project_name: str = Field(..., description="Name of analyzed project")
    timestamp: datetime = Field(..., description="Report generation timestamp")
    languages_analyzed: list[str] = Field(
        default_factory=list, description="Languages analyzed"
    )

    # Report sections
    executive_summary: ExecutiveSummary = Field(..., description="Executive summary")
    statistics: StatisticsOverview = Field(..., description="Statistics overview")
    prioritized_findings: list[FindingPriority] = Field(
        default_factory=list, description="Prioritized findings list"
    )
    recommendations: list[RecommendationItem] = Field(
        default_factory=list, description="Actionable recommendations"
    )

    # Additional context
    has_triage_data: bool = Field(
        default=False, description="Whether triage data was available"
    )
    has_detailed_assessments: bool = Field(
        default=False, description="Whether detailed assessments were available"
    )
    triage_count: int = Field(default=0, description="Number of triaged findings")
    detailed_assessment_count: int = Field(
        default=0, description="Number of detailed assessments"
    )

    def get_actionable_count(self) -> int:
        """Get count of critical and high severity findings."""
        return self.statistics.critical_count + self.statistics.high_count

    def get_high_priority_findings(self) -> list[FindingPriority]:
        """Get findings with priority score >= 0.7."""
        return [f for f in self.prioritized_findings if f.priority_score >= 0.7]

    def get_immediate_recommendations(self) -> list[RecommendationItem]:
        """Get recommendations with immediate priority."""
        return [r for r in self.recommendations if r.priority == "immediate"]
