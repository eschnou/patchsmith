"""Report generator agent for creating security analysis reports."""

from typing import TYPE_CHECKING

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.analysis import AnalysisResult
from patchsmith.models.finding import Finding, Severity
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


class ReportGeneratorAgent(BaseAgent):
    """Agent for generating human-readable security reports using Claude AI.

    This agent takes analysis results and generates comprehensive reports
    with executive summaries, prioritized findings, and actionable recommendations.
    """

    def get_system_prompt(self) -> str:
        """Get system prompt for report generation."""
        return """You are a technical security report writer.

Your expertise includes:
- Creating clear, actionable security reports
- Summarizing complex technical findings
- Prioritizing vulnerabilities by risk
- Providing remediation guidance
- Writing for both technical and executive audiences

Report Structure:
1. Executive Summary (2-3 paragraphs)
   - Overall security posture
   - Critical statistics
   - Key recommendations

2. Findings Overview
   - Statistics by severity
   - Most common vulnerability types
   - Trends and patterns

3. Prioritized Findings
   - Critical and high severity first
   - Include location, description, impact
   - Filter out likely false positives

4. Recommendations
   - Immediate actions for critical issues
   - Long-term security improvements
   - Process and tooling suggestions

Write in clear, professional technical language. Be specific and actionable."""

    async def execute(  # type: ignore[override]
        self,
        analysis_result: AnalysisResult,
        report_format: str = "markdown",
        include_false_positives: bool = False,
    ) -> str:
        """
        Generate security report from analysis results.

        Args:
            analysis_result: Analysis results to report on
            report_format: Format for the report ("markdown", "html", "text")
            include_false_positives: Whether to include likely false positives

        Returns:
            Generated report as string

        Raises:
            AgentError: If report generation fails
        """
        logger.info(
            "report_generation_started",
            agent=self.agent_name,
            finding_count=len(analysis_result.findings),
            format=report_format,
        )

        try:
            # Filter findings if needed
            findings_to_report = analysis_result.findings
            if not include_false_positives:
                findings_to_report = [
                    f for f in findings_to_report
                    if not f.is_likely_false_positive
                ]

            # Build generation prompt
            prompt = self._build_generation_prompt(
                analysis_result, findings_to_report, report_format
            )

            # Query Claude
            response = await self.query_claude(
                prompt=prompt,
                max_turns=1,  # Report generation is straightforward
                allowed_tools=[],  # No tools needed
            )

            logger.info(
                "report_generation_completed",
                agent=self.agent_name,
                report_length=len(response),
            )

            return response

        except Exception as e:
            logger.error(
                "report_generation_failed",
                agent=self.agent_name,
                error=str(e),
            )
            raise AgentError(f"Report generation failed: {e}") from e

    def _build_generation_prompt(
        self,
        analysis_result: AnalysisResult,
        findings_to_report: list,
        report_format: str,
    ) -> str:
        """
        Build prompt for report generation.

        Args:
            analysis_result: Full analysis results
            findings_to_report: Filtered findings to include
            report_format: Desired report format

        Returns:
            Generation prompt
        """
        # Build statistics summary
        stats = analysis_result.statistics
        stats_text = f"""
Statistics:
- Total findings: {len(findings_to_report)} (of {len(analysis_result.findings)} total)
- Critical: {stats.get_critical_count()}
- High: {stats.get_high_count()}
- Medium: {stats.by_severity.get(Severity.MEDIUM, 0)}
- Low: {stats.by_severity.get(Severity.LOW, 0)}
- Info: {stats.by_severity.get(Severity.INFO, 0)}
"""

        # Build top findings summary (up to 10)
        findings_text = "\n\n".join([
            self._format_finding(f, i + 1)
            for i, f in enumerate(findings_to_report[:10])
        ])

        if len(findings_to_report) > 10:
            findings_text += f"\n\n... and {len(findings_to_report) - 10} more findings"

        format_instruction = ""
        if report_format == "markdown":
            format_instruction = "\n\nFormat the report in Markdown with proper headings, lists, and code blocks."
        elif report_format == "html":
            format_instruction = "\n\nFormat the report in HTML with proper structure and styling."

        return f"""Generate a comprehensive security analysis report.

{stats_text}

Key Findings:
{findings_text}

Project analyzed: {analysis_result.project_name}
Languages: {', '.join(analysis_result.languages_analyzed) if analysis_result.languages_analyzed else 'Unknown'}
Analyzed at: {analysis_result.timestamp.isoformat()}{format_instruction}

Create a professional security report following the standard structure."""

    def _format_finding(self, finding: Finding, index: int) -> str:
        """
        Format a single finding for the prompt.

        Args:
            finding: Finding to format
            index: Finding number

        Returns:
            Formatted finding text
        """
        fp_indicator = ""
        if finding.false_positive_score:
            if finding.false_positive_score.is_false_positive:
                fp_indicator = f" [Likely FP: {finding.false_positive_score.score:.2f}]"

        cwe_info = f" ({finding.cwe.id})" if finding.cwe else ""

        return f"""Finding #{index}: {finding.rule_id}
- Severity: {finding.severity.value.upper()}{cwe_info}{fp_indicator}
- Location: {finding.location}
- Message: {finding.message}"""
