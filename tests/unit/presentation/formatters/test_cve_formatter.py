"""Tests for CVE formatter."""

from pathlib import Path

import pytest
from patchsmith.models.finding import (
    CWE,
    DetailedSecurityAssessment,
    Finding,
    RiskType,
    Severity,
)
from patchsmith.presentation.formatters.cve import CVEFormatter


class TestCVEFormatter:
    """Tests for CVE formatter."""

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
            false_positive_reasoning="This is a legitimate SQL injection vulnerability with no input validation.",
            attack_scenario="An attacker could craft malicious input to extract sensitive data or modify database records.",
            risk_type=RiskType.EXTERNAL_PENTEST,
            exploitability_score=0.8,
            impact_description="Complete database compromise, data theft, or data manipulation",
            remediation_priority="immediate",
        )

    @pytest.fixture
    def sample_assessment_false_positive(self) -> DetailedSecurityAssessment:
        """Create a sample false positive assessment."""
        return DetailedSecurityAssessment(
            finding_id="F-1",
            is_false_positive=True,
            false_positive_score=0.9,
            false_positive_reasoning="The input is validated by framework middleware before reaching this code.",
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
        formatter = CVEFormatter()
        result = formatter.format(sample_finding, sample_assessment_valid)

        # Check header
        assert "SECURITY VULNERABILITY REPORT: F-1" in result
        assert "Finding ID: F-1" in result
        assert "Rule ID: sql-injection" in result

        # Check classification
        assert "Severity: HIGH" in result
        assert "CWE: CWE-89" in result
        assert "CWE Name: SQL Injection" in result
        assert "Risk Type: External Penetration Test" in result

        # Check false positive section
        assert "FALSE POSITIVE ASSESSMENT" in result
        assert "Status: VALID SECURITY ISSUE" in result
        assert "10.00%" in result  # false_positive_score formatted as percentage

        # Check detailed sections (only for valid vulnerabilities)
        assert "AFFECTED COMPONENT" in result
        assert "src/database/query.py" in result
        assert "Lines: 42-45" in result

        assert "DESCRIPTION" in result
        assert "Unsanitized user input in SQL query" in result

        assert "CODE SNIPPET" in result
        assert "SELECT * FROM users" in result

        assert "ATTACK VECTOR" in result
        assert "extract sensitive data" in result

        assert "EXPLOITABILITY ANALYSIS" in result
        assert "80.00%" in result  # exploitability_score formatted

        assert "IMPACT" in result
        assert "database compromise" in result

        assert "REMEDIATION" in result
        assert "Priority: IMMEDIATE" in result

        assert "END OF REPORT" in result

    def test_format_false_positive(
        self, sample_finding: Finding, sample_assessment_false_positive: DetailedSecurityAssessment
    ) -> None:
        """Test formatting a false positive."""
        formatter = CVEFormatter()
        result = formatter.format(sample_finding, sample_assessment_false_positive)

        # Check header
        assert "SECURITY VULNERABILITY REPORT: F-1" in result

        # Check false positive section
        assert "FALSE POSITIVE ASSESSMENT" in result
        assert "Status: FALSE POSITIVE" in result
        assert "90.00%" in result  # false_positive_score

        # Check that detailed sections are NOT included for false positives
        assert "ATTACK VECTOR" not in result
        assert "EXPLOITABILITY ANALYSIS" not in result
        assert "IMPACT" not in result
        assert "REMEDIATION" not in result

        assert "END OF REPORT" in result

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

        formatter = CVEFormatter()
        result = formatter.format(finding, sample_assessment_valid)

        assert "Finding ID: F-2" in result
        assert "CWE:" not in result  # No CWE section

    def test_format_without_snippet(
        self, sample_assessment_valid: DetailedSecurityAssessment
    ) -> None:
        """Test formatting finding without code snippet."""
        finding = Finding(
            id="F-3",
            rule_id="test-rule",
            severity=Severity.LOW,
            cwe=CWE(id="CWE-123"),
            file_path=Path("src/test.py"),
            start_line=1,
            end_line=1,
            message="Test issue",
            snippet=None,
        )

        formatter = CVEFormatter()
        result = formatter.format(finding, sample_assessment_valid)

        assert "Finding ID: F-3" in result
        assert "CODE SNIPPET" not in result  # No snippet section

    def test_risk_type_formatting(self) -> None:
        """Test risk type formatting."""
        formatter = CVEFormatter()

        assert formatter._format_risk_type("external_pentest") == "External Penetration Test"
        assert formatter._format_risk_type("internal_abuse") == "Internal Abuse"
        assert formatter._format_risk_type("supply_chain") == "Supply Chain"
        assert formatter._format_risk_type("configuration") == "Configuration"
        assert formatter._format_risk_type("data_exposure") == "Data Exposure"
        assert formatter._format_risk_type("other") == "Other"

    def test_exploitability_levels(self) -> None:
        """Test exploitability level classification."""
        formatter = CVEFormatter()

        assert "HIGH" in formatter._get_exploitability_level(0.9)
        assert "MEDIUM" in formatter._get_exploitability_level(0.5)
        assert "LOW" in formatter._get_exploitability_level(0.2)

    def test_remediation_guidance(self) -> None:
        """Test remediation guidance generation."""
        formatter = CVEFormatter()

        immediate = formatter._get_remediation_guidance("immediate")
        assert "immediate attention" in immediate

        high = formatter._get_remediation_guidance("high")
        assert "current development cycle" in high

        medium = formatter._get_remediation_guidance("medium")
        assert "next release cycle" in medium

        low = formatter._get_remediation_guidance("low")
        assert "when convenient" in low
