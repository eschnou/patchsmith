"""CVE-style formatter for investigation results."""

from datetime import datetime

from patchsmith.models.finding import DetailedSecurityAssessment, Finding
from patchsmith.presentation.formatters.base import BaseFormatter


class CVEFormatter(BaseFormatter):
    """Formats investigation results as standard CVE report."""

    def format(self, finding: Finding, assessment: DetailedSecurityAssessment) -> str:
        """Format as CVE report.

        Args:
            finding: The security finding
            assessment: Detailed security assessment

        Returns:
            CVE-formatted report string
        """
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append(f"SECURITY VULNERABILITY REPORT: {finding.id}")
        lines.append("=" * 80)
        lines.append("")

        # Metadata
        lines.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Finding ID: {finding.id}")
        lines.append(f"Rule ID: {finding.rule_id}")
        lines.append("")

        # Classification
        lines.append("-" * 80)
        lines.append("CLASSIFICATION")
        lines.append("-" * 80)
        lines.append(f"Severity: {finding.severity.value.upper()}")
        if finding.cwe:
            lines.append(f"CWE: {finding.cwe.id}")
            if finding.cwe.name:
                lines.append(f"CWE Name: {finding.cwe.name}")
        lines.append(f"Risk Type: {self._format_risk_type(assessment.risk_type.value)}")
        lines.append("")

        # False Positive Assessment
        lines.append("-" * 80)
        lines.append("FALSE POSITIVE ASSESSMENT")
        lines.append("-" * 80)
        status = "FALSE POSITIVE" if assessment.is_false_positive else "VALID SECURITY ISSUE"
        lines.append(f"Status: {status}")
        lines.append(f"Confidence Score: {assessment.false_positive_score:.2%}")
        lines.append(f"Reasoning: {assessment.false_positive_reasoning}")
        lines.append("")

        # Only include detailed sections if it's a valid issue
        if not assessment.is_false_positive:
            # Affected Component
            lines.append("-" * 80)
            lines.append("AFFECTED COMPONENT")
            lines.append("-" * 80)
            lines.append(f"File: {finding.file_path}")
            lines.append(f"Lines: {finding.start_line}-{finding.end_line}")
            lines.append("")

            # Description
            lines.append("-" * 80)
            lines.append("DESCRIPTION")
            lines.append("-" * 80)
            lines.append(finding.message)
            lines.append("")

            # Code Snippet
            if finding.snippet:
                lines.append("-" * 80)
                lines.append("CODE SNIPPET")
                lines.append("-" * 80)
                lines.append(finding.snippet)
                lines.append("")

            # Attack Vector
            lines.append("-" * 80)
            lines.append("ATTACK VECTOR")
            lines.append("-" * 80)
            lines.append(assessment.attack_scenario)
            lines.append("")

            # Exploitability
            lines.append("-" * 80)
            lines.append("EXPLOITABILITY ANALYSIS")
            lines.append("-" * 80)
            lines.append(f"Exploitability Score: {assessment.exploitability_score:.2%}")
            exploit_level = self._get_exploitability_level(assessment.exploitability_score)
            lines.append(f"Difficulty Level: {exploit_level}")
            lines.append("")

            # Impact
            lines.append("-" * 80)
            lines.append("IMPACT")
            lines.append("-" * 80)
            lines.append(assessment.impact_description)
            lines.append("")

            # Remediation
            lines.append("-" * 80)
            lines.append("REMEDIATION")
            lines.append("-" * 80)
            lines.append(f"Priority: {assessment.remediation_priority.upper()}")
            lines.append("")
            lines.append(self._get_remediation_guidance(assessment.remediation_priority))
            lines.append("")

        # Footer
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)

    def _format_risk_type(self, risk_type: str) -> str:
        """Format risk type for display.

        Args:
            risk_type: Risk type value

        Returns:
            Formatted risk type string
        """
        type_map = {
            "external_pentest": "External Penetration Test",
            "internal_abuse": "Internal Abuse",
            "supply_chain": "Supply Chain",
            "configuration": "Configuration",
            "data_exposure": "Data Exposure",
            "other": "Other",
        }
        return type_map.get(risk_type, risk_type.title())

    def _get_exploitability_level(self, score: float) -> str:
        """Get exploitability difficulty level.

        Args:
            score: Exploitability score (0.0-1.0)

        Returns:
            Difficulty level description
        """
        if score >= 0.7:
            return "HIGH (Easy to exploit)"
        elif score >= 0.4:
            return "MEDIUM (Moderate difficulty)"
        else:
            return "LOW (Difficult to exploit)"

    def _get_remediation_guidance(self, priority: str) -> str:
        """Get remediation timeline guidance.

        Args:
            priority: Remediation priority level

        Returns:
            Remediation guidance text
        """
        guidance = {
            "immediate": "This vulnerability requires immediate attention and should be fixed "
            "as soon as possible. Consider emergency patching procedures.",
            "high": "This vulnerability should be addressed in the current development cycle "
            "or sprint. Prioritize this fix over non-security work.",
            "medium": "This vulnerability should be fixed in the next release cycle. "
            "Include in your next sprint or milestone planning.",
            "low": "This vulnerability can be addressed when convenient. Consider including "
            "in routine maintenance or technical debt work.",
        }
        return guidance.get(priority, "Address according to your security policies.")
