"""HTML formatter for security reports."""

import html as html_module

from markdown_it import MarkdownIt

from patchsmith.models.report import (
    FindingPriority,
    RecommendationItem,
    SecurityReportData,
)
from patchsmith.presentation.formatters.report_base import BaseReportFormatter


class ReportHtmlFormatter(BaseReportFormatter):
    """Formats security reports as HTML."""

    def __init__(self) -> None:
        """Initialize HTML formatter with markdown parser."""
        super().__init__()
        self.md = MarkdownIt()

    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown text to HTML.

        Args:
            text: Markdown-formatted text

        Returns:
            HTML-formatted text
        """
        if not text:
            return ""
        html_output: str = self.md.render(text)
        return html_output

    def format(self, report_data: SecurityReportData) -> str:
        """Format security report as HTML.

        Args:
            report_data: Structured security report data

        Returns:
            HTML-formatted report string
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

        # Build complete HTML document
        return self._build_html_document(report_data, "\n".join(sections))

    def _build_html_document(self, report_data: SecurityReportData, content: str) -> str:
        """Build complete HTML document with styling.

        Args:
            report_data: Report data for metadata
            content: HTML content sections

        Returns:
            Complete HTML document string
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Report - {html_module.escape(report_data.project_name)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 8px;
        }}

        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 30px;
            font-size: 2.5em;
        }}

        h2 {{
            color: #34495e;
            margin-top: 40px;
            margin-bottom: 20px;
            font-size: 1.8em;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 10px;
        }}

        h3 {{
            color: #555;
            margin-top: 30px;
            margin-bottom: 15px;
            font-size: 1.4em;
        }}

        h4 {{
            color: #666;
            margin-top: 25px;
            margin-bottom: 10px;
            font-size: 1.2em;
        }}

        .metadata {{
            background: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 30px;
        }}

        .metadata p {{
            margin: 5px 0;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
            margin-right: 5px;
        }}

        .severity-critical {{
            background: #e74c3c;
            color: white;
        }}

        .severity-high {{
            background: #e67e22;
            color: white;
        }}

        .severity-medium {{
            background: #f39c12;
            color: white;
        }}

        .severity-low {{
            background: #27ae60;
            color: white;
        }}

        .severity-info {{
            background: #3498db;
            color: white;
        }}

        .priority-immediate {{
            background: #c0392b;
            color: white;
        }}

        .priority-high {{
            background: #e67e22;
            color: white;
        }}

        .priority-medium {{
            background: #3498db;
            color: white;
        }}

        .priority-low {{
            background: #95a5a6;
            color: white;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}

        .stat-card {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 5px;
            text-align: center;
        }}

        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #2c3e50;
        }}

        .stat-label {{
            color: #7f8c8d;
            margin-top: 5px;
        }}

        .finding-card {{
            background: #f9f9f9;
            border: 1px solid #ddd;
            border-left: 4px solid #3498db;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
        }}

        .finding-card.critical {{
            border-left-color: #e74c3c;
        }}

        .finding-card.high {{
            border-left-color: #e67e22;
        }}

        .finding-card.medium {{
            border-left-color: #f39c12;
        }}

        .finding-card.low {{
            border-left-color: #27ae60;
        }}

        .finding-meta {{
            margin: 10px 0;
            font-size: 0.95em;
            color: #666;
        }}

        .finding-meta strong {{
            color: #2c3e50;
        }}

        .code {{
            background: #2c3e50;
            color: #ecf0f1;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}

        .alert {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 5px;
            padding: 15px;
            margin: 15px 0;
        }}

        .alert.danger {{
            background: #f8d7da;
            border-color: #f5c6cb;
        }}

        .alert.info {{
            background: #d1ecf1;
            border-color: #bee5eb;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}

        th {{
            background: #34495e;
            color: white;
            font-weight: bold;
        }}

        tr:hover {{
            background: #f5f5f5;
        }}

        ul {{
            margin: 15px 0;
            padding-left: 30px;
        }}

        li {{
            margin: 8px 0;
        }}

        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
        }}

        .recommendation-card {{
            background: #eef7ff;
            border: 1px solid #b8daff;
            border-radius: 5px;
            padding: 20px;
            margin: 20px 0;
        }}

        hr {{
            border: none;
            border-top: 1px solid #ecf0f1;
            margin: 30px 0;
        }}

        /* Markdown content styling */
        .content {{
            line-height: 1.7;
        }}

        .content p {{
            margin: 12px 0;
        }}

        .content ul, .content ol {{
            margin: 12px 0;
            padding-left: 30px;
        }}

        .content li {{
            margin: 6px 0;
        }}

        .content strong {{
            font-weight: 600;
            color: #2c3e50;
        }}

        .content code {{
            background: #f4f4f4;
            color: #e74c3c;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}

        .content pre {{
            background: #2c3e50;
            color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            margin: 15px 0;
        }}

        .content pre code {{
            background: transparent;
            color: inherit;
            padding: 0;
        }}

        .content blockquote {{
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin: 15px 0;
            color: #666;
            font-style: italic;
        }}

        .content h1, .content h2, .content h3, .content h4, .content h5, .content h6 {{
            margin-top: 20px;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
{content}
    </div>
</body>
</html>"""

    def _format_header(self, report_data: SecurityReportData) -> str:
        """Format report header."""
        languages = ", ".join(report_data.languages_analyzed) if report_data.languages_analyzed else "Unknown"

        return f"""<h1>🔒 Security Analysis Report</h1>
<div class="metadata">
    <p><strong>Project:</strong> {html_module.escape(report_data.project_name)}</p>
    <p><strong>Generated:</strong> {report_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Languages:</strong> {html_module.escape(languages)}</p>
</div>"""

    def _format_executive_summary(self, report_data: SecurityReportData) -> str:
        """Format executive summary section."""
        summary = report_data.executive_summary
        lines = [
            "<h2>📋 Executive Summary</h2>",
            f"<div class='content'>{self._markdown_to_html(summary.overall_assessment)}</div>",
            "",
            "<h3>Key Statistics</h3>",
            '<div class="stats-grid">',
            '    <div class="stat-card">',
            f'        <div class="stat-number">{summary.critical_findings_count}</div>',
            '        <div class="stat-label">Critical Findings</div>',
            '    </div>',
            '    <div class="stat-card">',
            f'        <div class="stat-number">{summary.high_findings_count}</div>',
            '        <div class="stat-label">High Severity</div>',
            '    </div>',
            '    <div class="stat-card">',
            f'        <div class="stat-number">{summary.critical_findings_count + summary.high_findings_count}</div>',
            '        <div class="stat-label">Total Actionable</div>',
            '    </div>',
            "</div>",
        ]

        if summary.key_risks:
            lines.append("<h3>Key Risk Areas</h3>")
            lines.append("<ul>")
            for risk in summary.key_risks:
                lines.append(f"    <li>{html_module.escape(risk)}</li>")
            lines.append("</ul>")

        if summary.immediate_actions:
            lines.append('<div class="alert danger">')
            lines.append("<h3>🚨 Immediate Actions Required</h3>")
            lines.append("<ol>")
            for action in summary.immediate_actions:
                lines.append(f"    <li>{html_module.escape(action)}</li>")
            lines.append("</ol>")
            lines.append("</div>")

        return "\n".join(lines)

    def _format_statistics(self, report_data: SecurityReportData) -> str:
        """Format statistics section."""
        stats = report_data.statistics
        lines = [
            "<h2>📊 Statistics Overview</h2>",
            f"<p><strong>Total Findings:</strong> {stats.total_findings}</p>",
            "",
            "<h3>Findings by Severity</h3>",
            "<table>",
            "    <thead>",
            "        <tr>",
            "            <th>Severity</th>",
            "            <th>Count</th>",
            "        </tr>",
            "    </thead>",
            "    <tbody>",
            f'        <tr><td><span class="badge severity-critical">🔴 Critical</span></td><td>{stats.critical_count}</td></tr>',
            f'        <tr><td><span class="badge severity-high">🟠 High</span></td><td>{stats.high_count}</td></tr>',
            f'        <tr><td><span class="badge severity-medium">🟡 Medium</span></td><td>{stats.medium_count}</td></tr>',
            f'        <tr><td><span class="badge severity-low">🟢 Low</span></td><td>{stats.low_count}</td></tr>',
            f'        <tr><td><span class="badge severity-info">ℹ️ Info</span></td><td>{stats.info_count}</td></tr>',
            "    </tbody>",
            "</table>",
        ]

        if stats.false_positives_filtered > 0:
            lines.append(f"<p><strong>False Positives Identified:</strong> {stats.false_positives_filtered}</p>")

        if stats.most_common_cwes:
            lines.append("<h3>Most Common Vulnerability Types (CWE)</h3>")
            lines.append("<ul>")
            for cwe, count in stats.most_common_cwes[:10]:
                lines.append(f"    <li><strong>{html_module.escape(cwe)}:</strong> {count} occurrence(s)</li>")
            lines.append("</ul>")

        if report_data.has_triage_data or report_data.has_detailed_assessments:
            lines.append('<div class="alert info">')
            if report_data.has_triage_data:
                lines.append(f"<p>{report_data.triage_count} findings were triaged and prioritized.</p>")
            if report_data.has_detailed_assessments:
                lines.append(f"<p>{report_data.detailed_assessment_count} findings received detailed security assessment.</p>")
            lines.append("</div>")

        return "\n".join(lines)

    def _format_prioritized_findings(self, report_data: SecurityReportData) -> str:
        """Format prioritized findings section."""
        lines = [
            "<h2>🎯 Prioritized Findings</h2>",
        ]

        if not report_data.prioritized_findings:
            lines.append("<p><em>No findings to report.</em></p>")
            return "\n".join(lines)

        # Add priority summary table
        priority_counts = self._count_by_priority(report_data.prioritized_findings)
        if priority_counts:
            lines.append("<h3>📊 Priority Overview</h3>")
            lines.append('<table style="width: 100%; border-collapse: collapse; margin: 20px 0;">')
            lines.append('  <thead>')
            lines.append('    <tr style="background: #ecf0f1;">')
            lines.append('      <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Priority</th>')
            lines.append('      <th style="padding: 12px; text-align: center; border: 1px solid #ddd;">Count</th>')
            lines.append('      <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Action Timeline</th>')
            lines.append('    </tr>')
            lines.append('  </thead>')
            lines.append('  <tbody>')
            if priority_counts.get("immediate", 0) > 0:
                lines.append('    <tr style="background: #fee; font-weight: bold;">')
                lines.append('      <td style="padding: 12px; border: 1px solid #ddd;">🚨 <strong>Immediate</strong></td>')
                lines.append(f'      <td style="padding: 12px; text-align: center; border: 1px solid #ddd;"><strong>{priority_counts["immediate"]}</strong></td>')
                lines.append('      <td style="padding: 12px; border: 1px solid #ddd;">Fix now (today)</td>')
                lines.append('    </tr>')
            if priority_counts.get("high", 0) > 0:
                lines.append('    <tr>')
                lines.append('      <td style="padding: 12px; border: 1px solid #ddd;">⚠️ High</td>')
                lines.append(f'      <td style="padding: 12px; text-align: center; border: 1px solid #ddd;">{priority_counts["high"]}</td>')
                lines.append('      <td style="padding: 12px; border: 1px solid #ddd;">Fix this week</td>')
                lines.append('    </tr>')
            if priority_counts.get("medium", 0) > 0:
                lines.append('    <tr>')
                lines.append('      <td style="padding: 12px; border: 1px solid #ddd;">📌 Medium</td>')
                lines.append(f'      <td style="padding: 12px; text-align: center; border: 1px solid #ddd;">{priority_counts["medium"]}</td>')
                lines.append('      <td style="padding: 12px; border: 1px solid #ddd;">Fix this month</td>')
                lines.append('    </tr>')
            if priority_counts.get("low", 0) > 0:
                lines.append('    <tr>')
                lines.append('      <td style="padding: 12px; border: 1px solid #ddd;">📝 Low</td>')
                lines.append(f'      <td style="padding: 12px; text-align: center; border: 1px solid #ddd;">{priority_counts["low"]}</td>')
                lines.append('      <td style="padding: 12px; border: 1px solid #ddd;">Fix when possible</td>')
                lines.append('    </tr>')
            lines.append('  </tbody>')
            lines.append('</table>')
            lines.append('<hr>')

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
        # Handle findings without remediation priority
        no_priority_findings = [
            f for f in report_data.prioritized_findings
            if not f.remediation_priority
        ]
        no_priority_findings.sort(key=lambda x: x.priority_score, reverse=True)

        # Immediate findings
        if immediate_findings:
            lines.append('<h3 style="color: #c0392b;">🚨 Immediate Action Required</h3>')
            lines.append(f'<p style="background: #fee; padding: 12px; border-left: 4px solid #c0392b; margin: 10px 0;"><strong>{len(immediate_findings)} finding(s) require immediate attention - fix today!</strong></p>')
            for finding in immediate_findings:
                lines.append(self._format_finding(finding))

        # High priority
        if high_findings:
            lines.append('<h3 style="color: #e67e22;">⚠️ High Priority</h3>')
            lines.append(f'<p style="background: #fef5e7; padding: 12px; border-left: 4px solid #e67e22; margin: 10px 0;"><strong>{len(high_findings)} finding(s) should be fixed this week</strong></p>')
            for finding in high_findings:
                lines.append(self._format_finding(finding))

        # Medium priority
        if medium_findings:
            lines.append('<h3 style="color: #3498db;">📌 Medium Priority</h3>')
            lines.append(f'<p style="background: #ebf5fb; padding: 12px; border-left: 4px solid #3498db; margin: 10px 0;"><strong>{len(medium_findings)} finding(s) should be addressed this month</strong></p>')
            for finding in medium_findings:
                lines.append(self._format_finding(finding))

        # Low priority
        if low_findings:
            lines.append('<h3 style="color: #95a5a6;">📝 Low Priority</h3>')
            lines.append(f'<p style="background: #f8f9f9; padding: 12px; border-left: 4px solid #95a5a6; margin: 10px 0;"><strong>{len(low_findings)} finding(s) - fix when convenient</strong></p>')
            for finding in low_findings:
                lines.append(self._format_finding(finding))

        # Other findings
        if no_priority_findings:
            lines.append("<h3>📋 Other Findings</h3>")
            for finding in no_priority_findings:
                lines.append(self._format_finding(finding))

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

    def _format_finding(self, finding: FindingPriority) -> str:
        """Format a single finding as HTML."""
        # Determine border color based on remediation priority (not severity)
        priority_colors = {
            "immediate": "#c0392b",
            "high": "#e67e22",
            "medium": "#3498db",
            "low": "#95a5a6"
        }
        border_color = priority_colors.get(
            finding.remediation_priority.lower() if finding.remediation_priority else "medium",
            "#95a5a6"
        )

        # Create priority bar visualization
        priority_pct = int(finding.priority_score * 100)
        priority_bar_filled = "█" * (priority_pct // 10)
        priority_bar_empty = "░" * (10 - priority_pct // 10)
        priority_bar = f"{priority_bar_filled}{priority_bar_empty}"

        lines = [
            f'<div class="finding-card" style="border-left-color: {border_color};">',
            f"    <h4>{html_module.escape(finding.title)}</h4>",
            '    <div class="finding-meta">',
            f'        <p><strong>Finding ID:</strong> <span class="code">{html_module.escape(finding.finding_id)}</span> | ',
            f'        <strong>Severity:</strong> <span class="badge severity-{finding.severity.lower()}">{self._get_severity_emoji(finding.severity)} {finding.severity.upper()}</span></p>',
            f'        <p><strong>📍 Location:</strong> <span class="code">{html_module.escape(finding.location)}</span></p>',
        ]

        if finding.cwe:
            lines.append(f'        <p><strong>🔖 CWE:</strong> {html_module.escape(finding.cwe)}</p>')

        # Priority score with visual bar
        lines.append(f'        <p><strong>⚡ Priority Score:</strong> {finding.priority_score:.2f} <code style="background: #2c3e50; color: #ecf0f1; padding: 2px 6px;">{priority_bar}</code> ({priority_pct}%)</p>')

        if finding.remediation_priority:
            priority_class = f"priority-{finding.remediation_priority.lower()}"
            lines.append(f'        <p><strong>🎯 Remediation Priority:</strong> <span class="badge {priority_class}">{self._get_priority_emoji(finding.remediation_priority)} {finding.remediation_priority.upper()}</span></p>')

        lines.append("    </div>")

        if finding.is_false_positive:
            lines.append('    <div class="alert">')
            lines.append("        <p>⚠️ <strong>Note:</strong> This finding is marked as a likely false positive.</p>")
            lines.append("    </div>")

        lines.append("    <p><strong>Description:</strong></p>")
        lines.append(f"    <div class='content'>{self._markdown_to_html(finding.description)}</div>")
        lines.append("    <p><strong>Prioritization Reasoning:</strong></p>")
        lines.append(f"    <div class='content'>{self._markdown_to_html(finding.reasoning)}</div>")

        # Detailed analysis
        if finding.attack_scenario and not finding.is_false_positive:
            lines.append("    <p><strong>Attack Scenario:</strong></p>")
            lines.append(f"    <div class='content'>{self._markdown_to_html(finding.attack_scenario)}</div>")

        if finding.impact_description and not finding.is_false_positive:
            lines.append("    <p><strong>Potential Impact:</strong></p>")
            lines.append(f"    <div class='content'>{self._markdown_to_html(finding.impact_description)}</div>")

        if finding.exploitability_score is not None and not finding.is_false_positive:
            exploit_level = "High" if finding.exploitability_score >= 0.7 else "Medium" if finding.exploitability_score >= 0.4 else "Low"
            lines.append(f"    <p><strong>Exploitability:</strong> {finding.exploitability_score:.0%} ({exploit_level})</p>")

        lines.append("</div>")

        return "\n".join(lines)

    def _format_recommendations(self, report_data: SecurityReportData) -> str:
        """Format recommendations section."""
        lines = [
            "<h2>💡 Recommendations</h2>",
        ]

        if not report_data.recommendations:
            lines.append("<p><em>No specific recommendations provided.</em></p>")
            return "\n".join(lines)

        # Group by priority
        immediate = [r for r in report_data.recommendations if r.priority.lower() == "immediate"]
        high = [r for r in report_data.recommendations if r.priority.lower() == "high"]
        medium = [r for r in report_data.recommendations if r.priority.lower() == "medium"]
        low = [r for r in report_data.recommendations if r.priority.lower() == "low"]

        # Immediate actions
        if immediate:
            lines.append("<h3>🚨 Immediate Actions</h3>")
            for rec in immediate:
                lines.append(self._format_recommendation(rec))

        # High priority
        if high:
            lines.append("<h3>⚠️ High Priority</h3>")
            for rec in high:
                lines.append(self._format_recommendation(rec))

        # Medium priority
        if medium:
            lines.append("<h3>📌 Medium Priority</h3>")
            for rec in medium:
                lines.append(self._format_recommendation(rec))

        # Low priority
        if low:
            lines.append("<h3>📝 Low Priority</h3>")
            for rec in low:
                lines.append(self._format_recommendation(rec))

        # Footer
        lines.append(self._format_footer(report_data))

        return "\n".join(lines)

    def _format_recommendation(self, recommendation: RecommendationItem) -> str:
        """Format a single recommendation as HTML."""
        lines = [
            '<div class="recommendation-card">',
            f"    <h4>{html_module.escape(recommendation.title)}</h4>",
            f"    <p><strong>Category:</strong> {html_module.escape(recommendation.category.title())}</p>",
        ]

        if recommendation.affected_findings:
            findings_list = ", ".join(f'<span class="code">{html_module.escape(fid)}</span>' for fid in recommendation.affected_findings)
            lines.append(f"    <p><strong>Addresses Findings:</strong> {findings_list}</p>")

        lines.append(f"    <div class='content'>{self._markdown_to_html(recommendation.description)}</div>")
        lines.append("</div>")

        return "\n".join(lines)

    def _format_footer(self, report_data: SecurityReportData) -> str:
        """Format report footer."""
        return f"""<div class="footer">
    <hr>
    <h2>📝 Report Information</h2>
    <p><strong>Report Generated:</strong> {report_data.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Project:</strong> {html_module.escape(report_data.project_name)}</p>
    <p><strong>Total Findings Analyzed:</strong> {report_data.statistics.total_findings}</p>
    <p><strong>Prioritized Findings:</strong> {len(report_data.prioritized_findings)}</p>
    <p><strong>Recommendations:</strong> {len(report_data.recommendations)}</p>
    <br>
    <p><em>Generated by Patchsmith Security Analysis Tool</em></p>
</div>"""
