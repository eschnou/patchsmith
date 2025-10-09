"""Report generator agent for creating security analysis reports."""

import json
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server, tool

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.analysis import AnalysisResult, TriageResult
from patchsmith.models.finding import DetailedSecurityAssessment, Finding, Severity
from patchsmith.models.report import (
    ExecutiveSummary,
    FindingPriority,
    RecommendationItem,
    SecurityReportData,
    StatisticsOverview,
)
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


class ReportGeneratorAgent(BaseAgent):
    """Agent for generating human-readable security reports using Claude AI.

    This agent takes analysis results and generates comprehensive reports
    with executive summaries, prioritized findings, and actionable recommendations.
    Returns structured data that can be formatted into various output formats.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize report generator agent with result storage."""
        super().__init__(*args, **kwargs)
        self._report_data: dict | None = None

    def _create_submit_tool(self) -> Any:
        """Create submit_report_data tool with closure to access instance state.

        Returns:
            Tool function that can access self._report_data
        """
        # Capture self in closure
        agent_instance = self

        @tool(
            "submit_report_content",
            "Submit narrative report content (agent-generated text only)",
            {
                "overall_assessment": str,  # 2-3 paragraphs on security posture
                "key_risks": list,  # List of 3-5 key risk areas
                "immediate_actions": list,  # List of 2-4 immediate actions
                "recommendations": list,  # List of {title: str, description: str, priority: str, category: str, affected_findings: list[str]}
            },
        )
        async def submit_report_data_tool(args: dict) -> dict:
            """Tool for submitting narrative report content."""
            # Handle JSON string input (entire args)
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    logger.error("submit_report_content_invalid_json", data=str(args)[:200])
                    return {"content": [{"type": "text", "text": "Error: Invalid JSON format"}]}

            # Parse nested JSON strings if needed
            def parse_list_field(value: Any, field_name: str) -> list:
                """Parse value as a list, handling JSON strings and various formats.

                Args:
                    value: Value to parse (could be list, JSON string, or other)
                    field_name: Name of field for logging

                Returns:
                    List (empty list if parsing fails)
                """
                # Already a list
                if isinstance(value, list):
                    return value

                # Try parsing JSON string
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return parsed
                        logger.warning(
                            "report_field_not_list",
                            field=field_name,
                            type=type(parsed).__name__,
                        )
                        return []
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            "report_field_parse_failed",
                            field=field_name,
                            value_preview=str(value)[:100],
                        )
                        return []

                # Fallback to empty list
                logger.warning(
                    "report_field_invalid_type",
                    field=field_name,
                    type=type(value).__name__,
                )
                return []

            # Store only narrative content from agent
            agent_instance._report_data = {
                "overall_assessment": args.get("overall_assessment", ""),
                "key_risks": parse_list_field(args.get("key_risks", []), "key_risks"),
                "immediate_actions": parse_list_field(
                    args.get("immediate_actions", []), "immediate_actions"
                ),
                "recommendations": parse_list_field(
                    args.get("recommendations", []), "recommendations"
                ),
            }

            recommendations_count = len(agent_instance._report_data["recommendations"])

            logger.info(
                "report_content_submitted",
                recommendations_count=recommendations_count,
            )

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Report content recorded: {recommendations_count} recommendations",
                    }
                ]
            }

        return submit_report_data_tool

    def get_system_prompt(self) -> str:
        """Get system prompt for report generation."""
        return """You are a technical security report writer who creates executive summaries and recommendations.

Your expertise includes:
- Summarizing complex technical findings for executive audiences
- Identifying key security risks and priorities
- Providing actionable remediation recommendations
- Writing clear, professional security guidance
- Recognizing systemic patterns across multiple vulnerability instances

**IMPORTANT - Grouped Findings:**
Some findings may be GROUPED, meaning multiple instances of the same vulnerability pattern were identified and consolidated into a single representative finding for efficiency.

When you see "[GROUP: X instances - pattern]" notation:
- This indicates a systemic issue appearing in X locations
- Your assessment should reflect the cumulative risk and scope
- Recommendations should address the pattern systematically, not just individual instances
- The impact is magnified by the number of instances

Your role is to provide NARRATIVE CONTENT ONLY:
1. overall_assessment - 2-3 paragraphs describing the overall security posture
2. key_risks - List of 3-5 key risk areas or vulnerability types
3. immediate_actions - List of 2-4 immediate actions needed for critical issues
4. recommendations - Actionable recommendations with priority and category

You have access to:
- submit_report_content: Submit your narrative content (YOU MUST call this)

Process:
1. Review the provided statistics, findings, and assessments
2. Write an overall assessment (2-3 paragraphs on security posture)
3. Identify 3-5 key risk areas
4. List 2-4 immediate actions for the most critical issues
5. Generate 5-10 actionable recommendations
6. Call submit_report_content tool with your narrative content

Each recommendation should have:
- title: Short title
- description: Detailed description (2-3 sentences)
- priority: immediate, high, medium, or low
- category: remediation, process, tooling, or training
- affected_findings: List of finding IDs this addresses (if applicable)

Be specific, technical, and actionable. Focus on the most critical issues first.
YOU MUST call the submit_report_content tool to report your content."""

    async def execute(  # type: ignore[override]
        self,
        analysis_result: AnalysisResult,
        triage_results: list[TriageResult] | None = None,
        detailed_assessments: dict[str, DetailedSecurityAssessment] | None = None,
    ) -> SecurityReportData:
        """
        Generate structured security report data from analysis results.

        Args:
            analysis_result: Analysis results with all findings
            triage_results: Optional triage results (prioritized findings)
            detailed_assessments: Optional detailed assessments (comprehensive analysis)

        Returns:
            Structured SecurityReportData object

        Raises:
            AgentError: If report generation fails
        """
        # Reset instance results
        self._report_data = None

        logger.info(
            "report_generation_started",
            agent=self.agent_name,
            finding_count=len(analysis_result.findings),
            has_triage=triage_results is not None,
            has_detailed=detailed_assessments is not None,
        )

        try:
            # Create MCP server with custom tool
            submit_tool = self._create_submit_tool()
            server = create_sdk_mcp_server(
                name="report-content",
                version="1.0.0",
                tools=[submit_tool],
            )

            # Build generation prompt
            prompt = self._build_generation_prompt(
                analysis_result, triage_results, detailed_assessments
            )

            # Configure options with custom tool
            options = ClaudeAgentOptions(
                system_prompt=self.get_system_prompt(),
                max_turns=50,  # Reduced - agent only writes narrative
                allowed_tools=["mcp__report-content__submit_report_content"],
                mcp_servers={"report-content": server},
                cwd=str(self.working_dir),
            )

            # Query Claude with custom client
            turn_count = 0
            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                async for message in client.receive_response():
                    message_type = type(message).__name__

                    # Track turns for progress
                    if message_type == "AssistantMessage":
                        turn_count += 1
                        self._emit_progress(turn_count)

                    # Extract and emit thinking updates
                    thinking = self._extract_thinking_from_message(message)
                    if thinking:
                        self._emit_thinking(thinking)

                    logger.debug(
                        "agent_received_message",
                        agent=self.agent_name,
                        message_type=message_type,
                    )

                    # Check for tool use
                    if message_type == "AssistantMessage" and hasattr(message, "content"):
                        for item in message.content if isinstance(message.content, list) else []:
                            if hasattr(item, "type") and item.type == "tool_use":
                                logger.info(
                                    "tool_use_detected",
                                    agent=self.agent_name,
                                    tool_name=getattr(item, "name", "unknown"),
                                )

                    # Log final result
                    if message_type == "ResultMessage":
                        logger.info(
                            "result_message_received",
                            agent=self.agent_name,
                            subtype=getattr(message, "subtype", "unknown"),
                            num_turns=getattr(message, "num_turns", 0),
                        )

            # Check if tool was called
            if self._report_data is None:
                raise AgentError("Agent did not call submit_report_content tool")

            # Build report from agent narrative + existing data
            report_data = self._build_report_from_data(
                self._report_data, analysis_result, triage_results, detailed_assessments
            )

            logger.info(
                "report_generation_completed",
                agent=self.agent_name,
                findings_count=len(report_data.prioritized_findings),
                recommendations_count=len(report_data.recommendations),
            )

            return report_data

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
    ) -> str:
        """
        Build prompt for report generation.

        Args:
            analysis_result: Full analysis results
            triage_results: Triage results (prioritization)
            detailed_assessments: Detailed security assessments

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
                    # Show group information if this is a grouped finding
                    if triage.is_group_representative:
                        group_info = f" [GROUP: {triage.total_instances} instances - {triage.group_pattern}]"
                        related_ids = ", ".join(triage.related_finding_ids[:3])
                        if len(triage.related_finding_ids) > 3:
                            related_ids += f", +{len(triage.related_finding_ids) - 3} more"
                        triage_text += f"{i}. {triage.finding_id}{group_info}\n   Related: {related_ids}\n   {triage.reasoning}\n"
                    else:
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

        return f"""Write narrative content for a security analysis report.

{stats_text}{triage_text}{detailed_text}

Project analyzed: {analysis_result.project_name}
Languages: {', '.join(analysis_result.languages_analyzed) if analysis_result.languages_analyzed else 'Unknown'}
Analyzed at: {analysis_result.timestamp.isoformat()}

Your task is to write:

1. overall_assessment (2-3 paragraphs)
   - Describe the overall security posture based on the findings above
   - Mention that there are {stats.get_critical_count()} critical and {stats.get_high_count()} high severity findings
   - Discuss the severity of the issues and their potential impact

2. key_risks (list of 3-5 items)
   - Identify the main types of vulnerabilities or risk areas
   - Based on the findings, triage results, and detailed assessments above

3. immediate_actions (list of 2-4 items)
   - Specify concrete actions needed to address critical issues
   - Be specific and actionable

4. recommendations (list of 5-10 items, each with: title, description, priority, category, affected_findings)
   - Generate actionable security recommendations
   - Cover remediation, process improvements, tooling, and training
   - Link recommendations to specific finding IDs where applicable
   - Priority: immediate, high, medium, or low
   - Category: remediation, process, tooling, or training

Call submit_report_content tool with your narrative content."""

    def _build_report_from_data(
        self,
        narrative_content: dict,
        analysis_result: AnalysisResult,
        triage_results: list[TriageResult] | None,
        detailed_assessments: dict[str, DetailedSecurityAssessment] | None,
    ) -> SecurityReportData:
        """
        Build SecurityReportData from existing data + agent narrative.

        Args:
            narrative_content: Agent-generated narrative content
            analysis_result: Original analysis result with findings and stats
            triage_results: Triage results for prioritization
            detailed_assessments: Detailed assessments for enrichment

        Returns:
            SecurityReportData object

        Raises:
            AgentError: If building fails
        """
        try:
            from datetime import datetime

            # Build executive summary from agent narrative + actual counts
            stats = analysis_result.statistics

            # Ensure list fields are actually lists
            key_risks = narrative_content.get("key_risks", [])
            if not isinstance(key_risks, list):
                logger.warning("key_risks_not_list", type=type(key_risks).__name__)
                key_risks = []

            immediate_actions = narrative_content.get("immediate_actions", [])
            if not isinstance(immediate_actions, list):
                logger.warning("immediate_actions_not_list", type=type(immediate_actions).__name__)
                immediate_actions = []

            executive_summary = ExecutiveSummary(
                overall_assessment=narrative_content.get("overall_assessment", ""),
                critical_findings_count=stats.get_critical_count(),
                high_findings_count=stats.get_high_count(),
                key_risks=key_risks,
                immediate_actions=immediate_actions,
            )

            # Build statistics directly from analysis_result
            # Calculate most common CWEs
            cwe_counts: dict[str, int] = {}
            for finding in analysis_result.findings:
                if finding.cwe:
                    cwe_id = finding.cwe.id
                    cwe_counts[cwe_id] = cwe_counts.get(cwe_id, 0) + 1

            most_common_cwes = sorted(cwe_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            statistics = StatisticsOverview(
                total_findings=len(analysis_result.findings),
                critical_count=stats.get_critical_count(),
                high_count=stats.get_high_count(),
                medium_count=stats.by_severity.get(Severity.MEDIUM, 0),
                low_count=stats.by_severity.get(Severity.LOW, 0),
                info_count=stats.by_severity.get(Severity.INFO, 0),
                false_positives_filtered=stats.false_positives_filtered,
                most_common_cwes=most_common_cwes,
            )

            # Build prioritized findings from triage + detailed assessments
            prioritized_findings = []
            if triage_results:
                # Use triage results to process ALL findings (not just recommended)
                for triage in triage_results:
                    # Find the actual finding
                    finding_match = next(
                        (f for f in analysis_result.findings if f.id == triage.finding_id),
                        None
                    )
                    if not finding_match:
                        continue

                    finding = finding_match

                    # Get detailed assessment if available (only for recommended findings)
                    assessment = None
                    if triage.recommended_for_analysis and detailed_assessments:
                        assessment = detailed_assessments.get(triage.finding_id)

                    # Collect related locations if this is a grouped finding
                    related_locations = []
                    if triage.related_finding_ids:
                        for related_id in triage.related_finding_ids:
                            related_finding = next(
                                (f for f in analysis_result.findings if f.id == related_id),
                                None
                            )
                            if related_finding:
                                related_locations.append(related_finding.location)

                    # Clean up the message (CodeQL data flow queries repeat message for each path)
                    # Take only the first occurrence to avoid repetition in reports
                    clean_message = finding.message.split('\n')[0] if finding.message else finding.message

                    # Build FindingPriority for ALL findings (recommended and non-recommended)
                    finding_priority = FindingPriority(
                        finding_id=finding.id,
                        title=finding.rule_id,  # Use rule_id as title
                        severity=finding.severity.value,
                        location=finding.location,
                        description=clean_message,
                        priority_score=triage.priority_score,
                        reasoning=triage.reasoning,
                        cwe=finding.cwe.id if finding.cwe else None,
                        # Grouping fields
                        related_finding_ids=triage.related_finding_ids,
                        group_pattern=triage.group_pattern,
                        related_locations=related_locations,
                        # Detailed analysis fields (only populated for recommended findings)
                        is_false_positive=assessment.is_false_positive if assessment else False,
                        attack_scenario=assessment.attack_scenario if assessment and not assessment.is_false_positive else None,
                        risk_type=assessment.risk_type.value if assessment and not assessment.is_false_positive else None,
                        exploitability_score=assessment.exploitability_score if assessment and not assessment.is_false_positive else None,
                        impact_description=assessment.impact_description if assessment and not assessment.is_false_positive else None,
                        remediation_priority=assessment.remediation_priority if assessment and not assessment.is_false_positive else None,
                    )
                    prioritized_findings.append(finding_priority)

            # Parse recommendations from agent
            recommendations = []
            for rec_data in narrative_content.get("recommendations", []):
                if not isinstance(rec_data, dict):
                    continue

                recommendation = RecommendationItem(
                    title=rec_data.get("title", ""),
                    description=rec_data.get("description", ""),
                    priority=rec_data.get("priority", "medium"),
                    category=rec_data.get("category", "remediation"),
                    affected_findings=rec_data.get("affected_findings", []),
                )
                recommendations.append(recommendation)

            # Create SecurityReportData
            report_data = SecurityReportData(
                project_name=analysis_result.project_name,
                timestamp=datetime.now(),
                languages_analyzed=analysis_result.languages_analyzed,
                executive_summary=executive_summary,
                statistics=statistics,
                prioritized_findings=prioritized_findings,
                recommendations=recommendations,
                has_triage_data=triage_results is not None,
                has_detailed_assessments=detailed_assessments is not None,
                triage_count=len(triage_results) if triage_results else 0,
                detailed_assessment_count=len(detailed_assessments) if detailed_assessments else 0,
            )

            return report_data

        except Exception as e:
            logger.error("report_build_error", error=str(e))
            raise AgentError(f"Failed to build report: {e}") from e

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
