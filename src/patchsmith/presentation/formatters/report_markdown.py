"""Markdown formatter for security reports."""

from patchsmith.models.report import (
    FindingPriority,
    RecommendationItem,
    SecurityReportData,
)
from patchsmith.presentation.formatters.report_base import BaseReportFormatter


class ReportMarkdownFormatter(BaseReportFormatter):
    """Formats security reports as markdown."""

    def format(self, report_data: SecurityReportData) -> str:
        """Format security report as markdown.

        Args:
            report_data: Structured security report data

        Returns:
            Markdown-formatted report string
        """
        sections = []

        # Header
        sections.append(self._format_header(report_data))

        # Executive Summary
        sections.append(self._format_executive_summary(report_data))

        # Statistics
        sections.append(self._format_statistics(report_data))

        # Prioritized Findings
        sections.append(self._format_prioritized_findings(report_data))

        # Recommendations
        sections.append(self._format_recommendations(report_data))

        # Footer
        sections.append(self._format_footer(report_data))

        return "\n\n".join(sections)

    def _format_header(self, report_data: SecurityReportData) -> str:
        """Format report header."""
        lines = [
            "# 🔒 Security Analysis Report",
            "",
            f"**Project:** {report_data.project_name}",
            f"**Generated:** {report_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if report_data.languages_analyzed:
            lines.append(f"**Languages:** {', '.join(report_data.languages_analyzed)}")

        lines.append("")
        lines.append("---")

        return "\n".join(lines)

    def _format_executive_summary(self, report_data: SecurityReportData) -> str:
        """Format executive summary section."""
        summary = report_data.executive_summary
        lines = [
            "## 📋 Executive Summary",
            "",
        ]

        # Format multiline overall assessment
        for line in summary.overall_assessment.split('\n'):
            lines.append(line)

        lines.extend([
            "",
            "### Key Statistics",
            "",
            f"- **Critical Findings:** {summary.critical_findings_count}",
            f"- **High Severity Findings:** {summary.high_findings_count}",
            f"- **Total Actionable Issues:** {summary.critical_findings_count + summary.high_findings_count}",
            "",
        ])

        if summary.key_risks:
            lines.append("### Key Risk Areas")
            lines.append("")
            for risk in summary.key_risks:
                lines.append(f"- {risk}")
            lines.append("")

        if summary.immediate_actions:
            lines.append("### Immediate Actions Required")
            lines.append("")
            for i, action in enumerate(summary.immediate_actions, 1):
                lines.append(f"{i}. {action}")
            lines.append("")

        return "\n".join(lines)

    def _format_statistics(self, report_data: SecurityReportData) -> str:
        """Format statistics section."""
        stats = report_data.statistics
        lines = [
            "## 📊 Statistics Overview",
            "",
            f"**Total Findings:** {stats.total_findings}",
            "",
            "### Findings by Severity",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| 🔴 Critical | {stats.critical_count} |",
            f"| 🟠 High | {stats.high_count} |",
            f"| 🟡 Medium | {stats.medium_count} |",
            f"| 🟢 Low | {stats.low_count} |",
            f"| ℹ️ Info | {stats.info_count} |",
            "",
        ]

        if stats.false_positives_filtered > 0:
            lines.append(
                f"**False Positives Identified:** {stats.false_positives_filtered}"
            )
            lines.append("")

        if stats.most_common_cwes:
            lines.append("### Most Common Vulnerability Types (CWE)")
            lines.append("")
            for cwe, count in stats.most_common_cwes[:10]:
                lines.append(f"- **{cwe}:** {count} occurrence(s)")
            lines.append("")

        # Add context about data sources
        if report_data.has_triage_data:
            lines.append(
                f"*{report_data.triage_count} findings were triaged and prioritized.*"
            )
        if report_data.has_detailed_assessments:
            lines.append(
                f"*{report_data.detailed_assessment_count} findings received detailed security assessment.*"
            )
        if report_data.has_triage_data or report_data.has_detailed_assessments:
            lines.append("")

        return "\n".join(lines)

    def _format_prioritized_findings(self, report_data: SecurityReportData) -> str:
        """Format prioritized findings section."""
        lines = [
            "## 🎯 Prioritized Findings",
            "",
        ]

        if not report_data.prioritized_findings:
            lines.append("*No findings to report.*")
            return "\n".join(lines)

        # Add priority summary table
        priority_counts = self._count_by_priority(report_data.prioritized_findings)
        if priority_counts:
            lines.append("### 📊 Priority Overview")
            lines.append("")
            lines.append("| Priority | Count | Action Timeline |")
            lines.append("|----------|-------|----------------|")
            if priority_counts.get("immediate", 0) > 0:
                lines.append(f"| 🚨 **Immediate** | **{priority_counts['immediate']}** | Fix now (today) |")
            if priority_counts.get("high", 0) > 0:
                lines.append(f"| ⚠️ High | {priority_counts['high']} | Fix this week |")
            if priority_counts.get("medium", 0) > 0:
                lines.append(f"| 📌 Medium | {priority_counts['medium']} | Fix this month |")
            if priority_counts.get("low", 0) > 0:
                lines.append(f"| 📝 Low | {priority_counts['low']} | Fix when possible |")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Group by remediation priority (not severity!)
        immediate_findings = [
            f for f in report_data.prioritized_findings
            if f.remediation_priority and f.remediation_priority.lower() == "immediate"
        ]
        high_findings = [
            f for f in report_data.prioritized_findings
            if f.remediation_priority and f.remediation_priority.lower() == "high"
        ]
        medium_findings = [
            f for f in report_data.prioritized_findings
            if f.remediation_priority and f.remediation_priority.lower() == "medium"
        ]
        low_findings = [
            f for f in report_data.prioritized_findings
            if f.remediation_priority and f.remediation_priority.lower() == "low"
        ]
        # Handle findings without remediation priority (sort by priority score)
        no_priority_findings = [
            f for f in report_data.prioritized_findings
            if not f.remediation_priority
        ]
        no_priority_findings.sort(key=lambda x: x.priority_score, reverse=True)

        # Immediate findings
        if immediate_findings:
            lines.append("### 🚨 Immediate Action Required")
            lines.append("")
            lines.append(f"**{len(immediate_findings)} finding(s) require immediate attention - fix today!**")
            lines.append("")
            for finding in immediate_findings:
                lines.extend(self._format_finding(finding))
            lines.append("")

        # High priority findings
        if high_findings:
            lines.append("### ⚠️ High Priority")
            lines.append("")
            lines.append(f"**{len(high_findings)} finding(s) should be fixed this week**")
            lines.append("")
            for finding in high_findings:
                lines.extend(self._format_finding(finding))
            lines.append("")

        # Medium priority findings
        if medium_findings:
            lines.append("### 📌 Medium Priority")
            lines.append("")
            lines.append(f"**{len(medium_findings)} finding(s) should be addressed this month**")
            lines.append("")
            for finding in medium_findings:
                lines.extend(self._format_finding(finding))
            lines.append("")

        # Low priority findings
        if low_findings:
            lines.append("### 📝 Low Priority")
            lines.append("")
            lines.append(f"**{len(low_findings)} finding(s) - fix when convenient**")
            lines.append("")
            for finding in low_findings:
                lines.extend(self._format_finding(finding))
            lines.append("")

        # Findings without remediation priority (lower-priority findings from triage, not deeply analyzed)
        if no_priority_findings:
            lines.append("### 📋 Additional Findings (Triaged, Not Deeply Analyzed)")
            lines.append("")
            lines.append(f"**{len(no_priority_findings)} finding(s) identified during triage** - These findings were analyzed and prioritized, but not selected for detailed AI security assessment. They are organized by priority score and include grouping information.")
            lines.append("")

            # Show a summary table for these
            lines.append("| Finding ID | Priority | Severity | Rule | Location |")
            lines.append("|------------|----------|----------|------|----------|")
            for finding in no_priority_findings[:20]:  # Limit detailed display
                group_indicator = f" 🔗×{finding.total_instances}" if finding.is_grouped else ""
                severity_emoji = self._get_severity_emoji(finding.severity)
                lines.append(f"| {finding.finding_id}{group_indicator} | {finding.priority_score:.2f} | {severity_emoji} {finding.severity.upper()} | {finding.title[:40]} | {finding.location[:40]} |")

            if len(no_priority_findings) > 20:
                lines.append("")
                lines.append(f"*... and {len(no_priority_findings) - 20} more lower-priority findings*")

            lines.append("")
            lines.append("💡 **Note**: To see detailed analysis of these findings, re-run analysis with `--investigate-all` flag.")
            lines.append("")

        return "\n".join(lines)

    def _count_by_priority(self, findings: list[FindingPriority]) -> dict[str, int]:
        """Count findings by remediation priority.

        Args:
            findings: List of findings to count

        Returns:
            Dictionary mapping priority to count
        """
        counts: dict[str, int] = {}
        for finding in findings:
            if finding.remediation_priority:
                priority = finding.remediation_priority.lower()
                counts[priority] = counts.get(priority, 0) + 1
        return counts

    def _format_finding(self, finding: FindingPriority) -> list[str]:
        """Format a single finding."""
        # Create severity badge
        severity_emoji = self._get_severity_emoji(finding.severity)
        severity_badge = f"{severity_emoji} {finding.severity.upper()}"

        # Create priority indicator
        priority_pct = int(finding.priority_score * 100)
        priority_bar = "█" * (priority_pct // 10) + "░" * (10 - priority_pct // 10)

        # Add group indicator to title if this is a grouped finding
        title = finding.title
        if finding.is_grouped:
            title = f"{finding.title} 🔗 ({finding.total_instances} instances)"

        lines = [
            f"#### {title}",
            "",
            f"**Finding ID:** `{finding.finding_id}` | **Severity:** {severity_badge}",
            "",
        ]

        # Show grouping information if applicable
        if finding.is_grouped:
            lines.append(f"**🔗 Grouped Finding:** {finding.total_instances} instances of the same pattern  ")
            if finding.group_pattern:
                lines.append(f"**📋 Pattern:** {finding.group_pattern}  ")
            lines.append("")
            lines.append("**Representative Location:**")
            lines.append(f"- `{finding.location}`")
            lines.append("")
            lines.append("**Related Instances:**")
            # Show first 5 related findings with locations
            for idx, (fid, loc) in enumerate(zip(finding.related_finding_ids[:5], finding.related_locations[:5])):
                lines.append(f"- `{fid}` at `{loc}`")
            if len(finding.related_finding_ids) > 5:
                lines.append(f"- *... and {len(finding.related_finding_ids) - 5} more instances*")
            lines.append("")
        else:
            lines.append(f"**📍 Location:** `{finding.location}`  ")
            lines.append("")

        if finding.cwe:
            lines.append(f"**🔖 CWE:** {finding.cwe}  ")

        # Show priority score with visual indicator
        lines.append(f"**⚡ Priority Score:** {finding.priority_score:.2f} `{priority_bar}` ({priority_pct}%)  ")

        if finding.remediation_priority:
            priority_emoji = self._get_priority_emoji(finding.remediation_priority)
            lines.append(f"**🎯 Remediation Priority:** {priority_emoji} {finding.remediation_priority.upper()}  ")

        lines.append("")

        if finding.is_false_positive:
            lines.append("")
            lines.append("⚠️ **Note:** This finding is marked as a likely false positive.")

        lines.append("")
        lines.append("**Description:**")
        lines.append("")
        for line in finding.description.split('\n'):
            lines.append(line)
        lines.append("")

        lines.append("**Prioritization Reasoning:**")
        lines.append("")
        for line in finding.reasoning.split('\n'):
            lines.append(line)
        lines.append("")

        # Detailed analysis (if available)
        if finding.attack_scenario and not finding.is_false_positive:
            lines.append("**Attack Scenario:**")
            lines.append("")
            # Format multiline text with proper indentation
            for line in finding.attack_scenario.split('\n'):
                lines.append(line)
            lines.append("")

        if finding.impact_description and not finding.is_false_positive:
            lines.append("**Potential Impact:**")
            lines.append("")
            # Format multiline text with proper indentation
            for line in finding.impact_description.split('\n'):
                lines.append(line)
            lines.append("")

        if finding.exploitability_score is not None and not finding.is_false_positive:
            exploit_level = "High" if finding.exploitability_score >= 0.7 else "Medium" if finding.exploitability_score >= 0.4 else "Low"
            lines.append(
                f"**Exploitability:** {finding.exploitability_score:.0%} ({exploit_level})"
            )
            lines.append("")

        lines.append("---")
        lines.append("")

        return lines

    def _format_recommendations(self, report_data: SecurityReportData) -> str:
        """Format recommendations section."""
        lines = [
            "## 💡 Recommendations",
            "",
        ]

        if not report_data.recommendations:
            lines.append("*No specific recommendations provided.*")
            return "\n".join(lines)

        # Group by priority
        immediate = [
            r for r in report_data.recommendations if r.priority.lower() == "immediate"
        ]
        high = [r for r in report_data.recommendations if r.priority.lower() == "high"]
        medium = [
            r for r in report_data.recommendations if r.priority.lower() == "medium"
        ]
        low = [r for r in report_data.recommendations if r.priority.lower() == "low"]

        # Immediate actions
        if immediate:
            lines.append("### 🚨 Immediate Actions")
            lines.append("")
            for rec in immediate:
                lines.extend(self._format_recommendation(rec))
            lines.append("")

        # High priority
        if high:
            lines.append("### ⚠️ High Priority")
            lines.append("")
            for rec in high:
                lines.extend(self._format_recommendation(rec))
            lines.append("")

        # Medium priority
        if medium:
            lines.append("### 📌 Medium Priority")
            lines.append("")
            for rec in medium:
                lines.extend(self._format_recommendation(rec))
            lines.append("")

        # Low priority
        if low:
            lines.append("### 📝 Low Priority")
            lines.append("")
            for rec in low:
                lines.extend(self._format_recommendation(rec))
            lines.append("")

        return "\n".join(lines)

    def _format_recommendation(self, recommendation: RecommendationItem) -> list[str]:
        """Format a single recommendation."""
        lines = [
            f"#### {recommendation.title}",
            "",
            f"**Category:** {recommendation.category.title()}  ",
        ]

        if recommendation.affected_findings:
            findings_list = ", ".join(f"`{fid}`" for fid in recommendation.affected_findings)
            lines.append(f"**Addresses Findings:** {findings_list}  ")

        lines.append("")
        # Format multiline description
        for line in recommendation.description.split('\n'):
            lines.append(line)
        lines.append("")

        return lines

    def _format_footer(self, report_data: SecurityReportData) -> str:
        """Format report footer."""
        lines = [
            "---",
            "",
            "## 📝 Report Information",
            "",
            f"- **Report Generated:** {report_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **Project:** {report_data.project_name}",
            f"- **Total Findings Analyzed:** {report_data.statistics.total_findings}",
            f"- **Prioritized Findings:** {len(report_data.prioritized_findings)}",
            f"- **Recommendations:** {len(report_data.recommendations)}",
            "",
            "*Generated by Patchsmith Security Analysis Tool*",
        ]

        return "\n".join(lines)
