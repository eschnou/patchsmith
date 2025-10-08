"""Report generator agent for creating security analysis reports."""

from typing import TYPE_CHECKING

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.analysis import AnalysisResult, TriageResult
from patchsmith.models.finding import DetailedSecurityAssessment, Finding, Severity
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
        triage_results: list[TriageResult] | None = None,
        detailed_assessments: dict[str, DetailedSecurityAssessment] | None = None,
        report_format: str = "markdown",
    ) -> str:
        """
        Generate security report from analysis results.

        Args:
            analysis_result: Analysis results with all findings
            triage_results: Optional triage results (prioritized findings)
            detailed_assessments: Optional detailed assessments (comprehensive analysis)
            report_format: Format for the report ("markdown", "html", "text")

        Returns:
            Generated report as string

        Raises:
            AgentError: If report generation fails
        """
        logger.info(
            "report_generation_started",
            agent=self.agent_name,
            finding_count=len(analysis_result.findings),
            has_triage=triage_results is not None,
            has_detailed=detailed_assessments is not None,
            format=report_format,
        )

        try:
            # Build generation prompt
            prompt = self._build_generation_prompt(
                analysis_result, triage_results, detailed_assessments, report_format
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
        triage_results: list[TriageResult] | None,
        detailed_assessments: dict[str, DetailedSecurityAssessment] | None,
        report_format: str,
    ) -> str:
        """
        Build prompt for report generation.

        Args:
            analysis_result: Full analysis results
            triage_results: Triage results (prioritization)
            detailed_assessments: Detailed security assessments
            report_format: Desired report format

        Returns:
            Generation prompt
        """
        # Build statistics summary
        stats = analysis_result.statistics
        stats_text = f"""
Statistics:
- Total findings: {len(analysis_result.findings)}
- Critical: {stats.get_critical_count()}
- High: {stats.get_high_count()}
- Medium: {stats.by_severity.get(Severity.MEDIUM, 0)}
- Low: {stats.by_severity.get(Severity.LOW, 0)}
- Info: {stats.by_severity.get(Severity.INFO, 0)}
"""

        # Build triage summary if available
        triage_text = ""
        if triage_results:
            recommended = [t for t in triage_results if t.recommended_for_analysis]
            triage_text = f"\n\nTriage Results:\n- {len(triage_results)} findings prioritized\n- {len(recommended)} recommended for detailed analysis\n"
            if recommended:
                triage_text += "\nTop Priority Findings:\n"
                for i, triage in enumerate(recommended[:5], 1):
                    triage_text += f"{i}. {triage.finding_id} (priority: {triage.priority_score:.2f})\n   {triage.reasoning}\n"

        # Build detailed assessments if available
        detailed_text = ""
        if detailed_assessments:
            detailed_text = f"\n\nDetailed Security Assessments ({len(detailed_assessments)} findings analyzed):\n\n"
            for finding_id, assessment in list(detailed_assessments.items())[:10]:  # Top 10
                # Find the actual finding for more context
                finding = next((f for f in analysis_result.findings if f.id == finding_id), None)
                if not finding:
                    continue

                detailed_text += f"Finding: {finding_id}\n"
                detailed_text += f"  Location: {finding.location}\n"
                detailed_text += f"  False Positive: {'YES' if assessment.is_false_positive else 'NO'} (confidence: {assessment.false_positive_score:.2f})\n"
                if not assessment.is_false_positive:
                    detailed_text += f"  Attack Scenario: {assessment.attack_scenario[:150]}...\n"
                    detailed_text += f"  Risk Type: {assessment.risk_type.value}\n"
                    detailed_text += f"  Exploitability: {assessment.exploitability_score:.2f}\n"
                    detailed_text += f"  Impact: {assessment.impact_description[:150]}...\n"
                    detailed_text += f"  Priority: {assessment.remediation_priority.upper()}\n"
                detailed_text += "\n"

        format_instruction = ""
        if report_format == "markdown":
            format_instruction = "\n\nFormat the report in Markdown with proper headings, lists, and code blocks."
        elif report_format == "html":
            format_instruction = "\n\nFormat the report in HTML with proper structure and styling."

        return f"""Generate a comprehensive security analysis report.

{stats_text}{triage_text}{detailed_text}

Project analyzed: {analysis_result.project_name}
Languages: {', '.join(analysis_result.languages_analyzed) if analysis_result.languages_analyzed else 'Unknown'}
Analyzed at: {analysis_result.timestamp.isoformat()}{format_instruction}

Create a professional security report with:
1. Executive Summary (highlighting most critical issues)
2. Overview Statistics
3. Prioritized Findings (focus on high-priority items from detailed analysis)
4. Detailed Analysis (for assessed findings, include attack scenarios and remediation priorities)
5. Recommendations

Use the triage results to show which issues were prioritized and why.
Use the detailed assessments to provide depth on attack scenarios and impacts."""

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
