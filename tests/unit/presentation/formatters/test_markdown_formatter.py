"""Tests for Markdown formatter."""

from pathlib import Path

import pytest
from patchsmith.models.finding import (
    CWE,
    DetailedSecurityAssessment,
    Finding,
    RiskType,
    Severity,
)
from patchsmith.presentation.formatters.markdown import MarkdownFormatter


class TestMarkdownFormatter:
    """Tests for Markdown formatter."""

    @pytest.fixture
    def sample_finding(self) -> Finding:
        """Create a sample finding for testing."""
        return Finding(
            id="F-1",
            rule_id="sql-injection",
            severity=Severity.HIGH,
            cwe=CWE(id="CWE-89", name="SQL Injection"),
            file_path=Path("src/database/query.py"),
            start_line=42,
            end_line=45,
            message="Unsanitized user input in SQL query",
            snippet='cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        )

    @pytest.fixture
    def sample_assessment_valid(self) -> DetailedSecurityAssessment:
        """Create a sample valid vulnerability assessment."""
        return DetailedSecurityAssessment(
            finding_id="F-1",
            is_false_positive=False,
            false_positive_score=0.1,
            false_positive_reasoning="This is a legitimate SQL injection vulnerability.",
            attack_scenario="An attacker could craft malicious input to extract sensitive data.",
            risk_type=RiskType.EXTERNAL_PENTEST,
            exploitability_score=0.8,
            impact_description="Complete database compromise",
            remediation_priority="immediate",
        )

    @pytest.fixture
    def sample_assessment_false_positive(self) -> DetailedSecurityAssessment:
        """Create a sample false positive assessment."""
        return DetailedSecurityAssessment(
            finding_id="F-1",
            is_false_positive=True,
            false_positive_score=0.9,
            false_positive_reasoning="The input is validated by framework middleware.",
            attack_scenario="N/A",
            risk_type=RiskType.OTHER,
            exploitability_score=0.0,
            impact_description="N/A",
            remediation_priority="low",
        )

    def test_format_valid_vulnerability(
        self, sample_finding: Finding, sample_assessment_valid: DetailedSecurityAssessment
    ) -> None:
        """Test formatting a valid vulnerability."""
        formatter = MarkdownFormatter()
        result = formatter.format(sample_finding, sample_assessment_valid)

        # Check header with Rich markup
        assert "[bold cyan]🔍 Investigation Results: F-1[/bold cyan]" in result

        # Check finding details
        assert "[bold]Finding Details:[/bold]" in result
        assert "ID: F-1" in result
        assert "Rule: sql-injection" in result
        assert "Severity: HIGH" in result
        assert "CWE: CWE-89" in result
        assert "src/database/query.py:42" in result

        # Check false positive section (red color for valid issue)
        assert "[red]" in result
        assert "VALID SECURITY ISSUE" in result
        assert "legitimate SQL injection" in result

        # Check attack scenario (yellow)
        assert "[yellow]" in result
        assert "Attack Scenario" in result
        assert "extract sensitive data" in result

        # Check risk analysis (cyan)
        assert "Risk Analysis" in result
        assert "[cyan]" in result
        assert "External Penetration Test" in result
        assert "80.0%" in result  # exploitability
        assert "[red]High[/red]" in result  # exploitability level
        assert "database compromise" in result
        assert "[red]IMMEDIATE[/red]" in result  # priority

        # Check next steps
        assert "Next Steps" in result
        assert "patchsmith fix F-1" in result
        assert "patchsmith list" in result

    def test_format_false_positive(
        self, sample_finding: Finding, sample_assessment_false_positive: DetailedSecurityAssessment
    ) -> None:
        """Test formatting a false positive."""
        formatter = MarkdownFormatter()
        result = formatter.format(sample_finding, sample_assessment_false_positive)

        # Check header
        assert "Investigation Results: F-1" in result

        # Check false positive section (green color)
        assert "[green]" in result
        assert "FALSE POSITIVE" in result
        assert "validated by framework" in result

        # Check that detailed analysis sections are NOT included
        assert "Attack Scenario" not in result
        assert "Risk Analysis" not in result

        # Check next steps for false positive
        assert "false positive" in result.lower()
        assert "excluding" in result.lower()

    def test_format_without_cwe(
        self, sample_assessment_valid: DetailedSecurityAssessment
    ) -> None:
        """Test formatting finding without CWE."""
        finding = Finding(
            id="F-2",
            rule_id="custom-rule",
            severity=Severity.MEDIUM,
            cwe=None,
            file_path=Path("src/app.py"),
            start_line=10,
            end_line=10,
            message="Custom security issue",
        )

        formatter = MarkdownFormatter()
        result = formatter.format(finding, sample_assessment_valid)

        assert "ID: F-2" in result
        # Should not have CWE line if no CWE
        lines = result.split("\n")
        cwe_lines = [line for line in lines if "CWE:" in line]
        assert len(cwe_lines) == 0

    def test_risk_type_formatting(self) -> None:
        """Test risk type formatting."""
        formatter = MarkdownFormatter()

        assert formatter._format_risk_type("external_pentest") == "External Penetration Test"
        assert formatter._format_risk_type("internal_abuse") == "Internal Abuse"
        assert formatter._format_risk_type("supply_chain") == "Supply Chain"
        assert formatter._format_risk_type("configuration") == "Configuration"
        assert formatter._format_risk_type("data_exposure") == "Data Exposure"
        assert formatter._format_risk_type("other") == "Other"

    def test_exploitability_levels_with_colors(self) -> None:
        """Test exploitability level classification with colors."""
        formatter = MarkdownFormatter()

        high = formatter._get_exploitability_level(0.9)
        assert "[red]High[/red]" == high

        medium = formatter._get_exploitability_level(0.5)
        assert "[yellow]Medium[/yellow]" == medium

        low = formatter._get_exploitability_level(0.2)
        assert "[green]Low[/green]" == low

    def test_priority_colors(self) -> None:
        """Test remediation priority colors."""
        formatter = MarkdownFormatter()

        assert formatter._get_priority_color("immediate") == "red"
        assert formatter._get_priority_color("high") == "yellow"
        assert formatter._get_priority_color("medium") == "blue"
        assert formatter._get_priority_color("low") == "green"

    def test_exploitability_score_boundaries(
        self, sample_finding: Finding
    ) -> None:
        """Test exploitability score boundary conditions."""
        formatter = MarkdownFormatter()

        # Test boundary at 0.7 (high)
        assessment_high = DetailedSecurityAssessment(
            finding_id="F-1",
            is_false_positive=False,
            false_positive_score=0.0,
            false_positive_reasoning="Test",
            attack_scenario="Test",
            risk_type=RiskType.EXTERNAL_PENTEST,
            exploitability_score=0.7,
            impact_description="Test",
            remediation_priority="high",
        )
        result_high = formatter.format(sample_finding, assessment_high)
        assert "[red]High[/red]" in result_high

        # Test boundary at 0.4 (medium)
        assessment_medium = DetailedSecurityAssessment(
            finding_id="F-1",
            is_false_positive=False,
            false_positive_score=0.0,
            false_positive_reasoning="Test",
            attack_scenario="Test",
            risk_type=RiskType.EXTERNAL_PENTEST,
            exploitability_score=0.4,
            impact_description="Test",
            remediation_priority="medium",
        )
        result_medium = formatter.format(sample_finding, assessment_medium)
        assert "[yellow]Medium[/yellow]" in result_medium

        # Test low
        assessment_low = DetailedSecurityAssessment(
            finding_id="F-1",
            is_false_positive=False,
            false_positive_score=0.0,
            false_positive_reasoning="Test",
            attack_scenario="Test",
            risk_type=RiskType.EXTERNAL_PENTEST,
            exploitability_score=0.3,
            impact_description="Test",
            remediation_priority="low",
        )
        result_low = formatter.format(sample_finding, assessment_low)
        assert "[green]Low[/green]" in result_low
