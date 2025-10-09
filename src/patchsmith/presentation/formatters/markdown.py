"""Markdown formatter for investigation results (Rich-compatible)."""

from patchsmith.models.finding import DetailedSecurityAssessment, Finding
from patchsmith.presentation.formatters.base import BaseFormatter


class MarkdownFormatter(BaseFormatter):
    """Formats investigation results as Rich-compatible markdown."""

    def format(self, finding: Finding, assessment: DetailedSecurityAssessment) -> str:
        """Format as Rich-compatible markdown.

        Args:
            finding: The security finding
            assessment: Detailed security assessment

        Returns:
            Markdown-formatted string with Rich markup
        """
        lines = []

        # Header
        lines.append(f"\n[bold cyan]🔍 Investigation Results: {finding.id}[/bold cyan]\n")

        # Finding Details
        lines.append("[bold]Finding Details:[/bold]")
        lines.append(f"  • ID: {finding.id}")
        lines.append(f"  • Rule: {finding.rule_id}")
        lines.append(f"  • Severity: {finding.severity.value.upper()}")
        if finding.cwe:
            lines.append(f"  • CWE: {finding.cwe.id}")
        lines.append(f"  • Location: {finding.file_path}:{finding.start_line}")
        lines.append("")

        # False Positive Assessment (Panel)
        fp_color = "red" if not assessment.is_false_positive else "green"
        status = "FALSE POSITIVE" if assessment.is_false_positive else "VALID SECURITY ISSUE"
        lines.append(f"[{fp_color}]{'─' * 80}[/{fp_color}]")
        lines.append(f"[{fp_color} bold]{status}[/{fp_color} bold]")
        lines.append(f"[{fp_color}]{'─' * 80}[/{fp_color}]")
        lines.append(f"\n{assessment.false_positive_reasoning}\n")

        # Only show detailed analysis if it's a valid issue
        if not assessment.is_false_positive:
            # Attack Scenario
            lines.append("[yellow]" + "─" * 80 + "[/yellow]")
            lines.append("[yellow bold]Attack Scenario[/yellow bold]")
            lines.append("[yellow]" + "─" * 80 + "[/yellow]")
            lines.append(f"\n{assessment.attack_scenario}\n")

            # Risk Analysis
            lines.append("[cyan]" + "─" * 80 + "[/cyan]")
            lines.append("[cyan bold]Risk Analysis[/cyan bold]")
            lines.append("[cyan]" + "─" * 80 + "[/cyan]")
            lines.append("")

            lines.append(f"[cyan]Risk Type:[/cyan] {self._format_risk_type(assessment.risk_type.value)}")

            # Exploitability
            exploit_level = self._get_exploitability_level(assessment.exploitability_score)
            lines.append(
                f"[cyan]Exploitability:[/cyan] {assessment.exploitability_score:.1%} - {exploit_level}"
            )

            # Impact
            lines.append(f"[cyan]Impact:[/cyan] {assessment.impact_description}")

            # Remediation Priority
            priority_color = self._get_priority_color(assessment.remediation_priority)
            lines.append(
                f"[cyan]Remediation Priority:[/cyan] [{priority_color}]{assessment.remediation_priority.upper()}[/{priority_color}]"
            )
            lines.append("")

            # Next Steps
            lines.append("[bold cyan]Next Steps:[/bold cyan]")
            lines.append(f"  • Fix this issue: [green]patchsmith fix {finding.id}[/green]")
            lines.append("  • View all findings: [green]patchsmith list[/green]")
        else:
            # Next steps for false positive
            lines.append("[bold cyan]Next Steps:[/bold cyan]")
            lines.append(
                "  • This appears to be a false positive. Consider excluding it from reports."
            )

        lines.append("")
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
        """Get exploitability difficulty level with color.

        Args:
            score: Exploitability score (0.0-1.0)

        Returns:
            Colored level string
        """
        if score >= 0.7:
            return "[red]High[/red]"
        elif score >= 0.4:
            return "[yellow]Medium[/yellow]"
        else:
            return "[green]Low[/green]"

    def _get_priority_color(self, priority: str) -> str:
        """Get color for remediation priority.

        Args:
            priority: Remediation priority level

        Returns:
            Color name
        """
        colors = {
            "immediate": "red",
            "high": "yellow",
            "medium": "blue",
            "low": "green",
        }
        return colors.get(priority, "white")
