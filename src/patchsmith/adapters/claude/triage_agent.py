"""Triage agent for prioritizing security findings."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server, tool

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.analysis import TriageResult
from patchsmith.models.finding import Finding
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


# Storage for tool results
_triage_results: list[dict] | None = None


@tool(
    "submit_triage_results",
    "Submit prioritized findings after triage analysis",
    {
        "prioritized_findings": list,  # List of {finding_id: str, priority_score: float, reasoning: str, recommended_for_analysis: bool}
    },
)
async def submit_triage_results_tool(args: dict) -> dict:
    """Tool for submitting triage results."""
    global _triage_results

    # Handle JSON string input
    prioritized = args.get("prioritized_findings", [])
    if isinstance(prioritized, str):
        try:
            prioritized = json.loads(prioritized)
        except json.JSONDecodeError:
            logger.error("submit_triage_invalid_json", data=str(prioritized)[:200])
            return {
                "content": [
                    {"type": "text", "text": "Error: Invalid JSON format"}
                ]
            }

    _triage_results = prioritized

    recommended_count = sum(1 for item in prioritized if item.get("recommended_for_analysis", False))

    logger.info(
        "triage_results_submitted",
        total_prioritized=len(prioritized),
        recommended_for_analysis=recommended_count,
    )

    return {
        "content": [
            {
                "type": "text",
                "text": f"Triage complete: {len(prioritized)} findings prioritized, {recommended_count} recommended for detailed analysis",
            }
        ]
    }


class TriageAgent(BaseAgent):
    """Agent for triaging and prioritizing security findings.

    This agent analyzes all findings at a high level to identify the most
    critical issues that warrant detailed investigation. It considers severity,
    vulnerability type, context, and potential impact to create a prioritized list.
    """

    def get_system_prompt(self) -> str:
        """Get system prompt for triage."""
        return """You are a security triage expert who prioritizes vulnerabilities for investigation.

Your expertise includes:
- Risk assessment and prioritization
- Understanding vulnerability criticality
- Identifying patterns in security findings
- Balancing severity, exploitability, and impact
- Recognizing common false positive patterns

When triaging findings, consider:
- Severity level (critical > high > medium > low)
- Vulnerability type (SQL injection, XSS, etc.)
- Location and context (production code vs tests, public-facing vs internal)
- Potential impact and exploitability
- Likelihood of being a false positive
- Patterns across multiple findings

You have access to:
- submit_triage_results: Submit your prioritization (YOU MUST call this with your results)

Process:
1. Review all findings provided in the prompt
2. Analyze patterns, severity distribution, and vulnerability types
3. Prioritize top 10-20 findings that need detailed investigation
4. For each prioritized finding, assign a priority score (0.0-1.0) and provide reasoning
5. Call submit_triage_results tool with your prioritized list

The submit_triage_results tool expects:
{
  "prioritized_findings": [
    {
      "finding_id": "sql-injection_app.py_42",
      "priority_score": 0.95,
      "reasoning": "Critical SQL injection in authentication code with user input",
      "recommended_for_analysis": true
    },
    ...
  ]
}

Requirements:
- finding_id: exact ID from the findings list
- priority_score: float 0.0-1.0 (higher = more critical)
- reasoning: brief explanation (1-2 sentences)
- recommended_for_analysis: true for top findings, false for lower priority

Select 10-20 findings for detailed analysis. Focus on:
- Highest severity with clear exploitation paths
- Vulnerabilities in critical code paths
- Issues with significant potential impact
- Findings that are unlikely to be false positives

YOU MUST call the submit_triage_results tool to report your prioritization."""

    async def execute(  # type: ignore[override]
        self,
        findings: list[Finding],
        csv_path: Path | None = None,
        top_n: int = 20,
    ) -> list[TriageResult]:
        """
        Triage findings and return prioritized list.

        Args:
            findings: List of all findings to triage
            csv_path: Optional path to CSV file with findings (lighter weight)
            top_n: Maximum number of findings to prioritize for detailed analysis

        Returns:
            List of TriageResult objects sorted by priority (highest first)

        Raises:
            AgentError: If triage fails
        """
        global _triage_results
        _triage_results = None  # Reset

        logger.info(
            "triage_started",
            agent=self.agent_name,
            total_findings=len(findings),
            top_n=top_n,
        )

        try:
            # Create MCP server with custom tool
            server = create_sdk_mcp_server(
                name="triage",
                version="1.0.0",
                tools=[submit_triage_results_tool],
            )

            # Build triage prompt
            prompt = self._build_triage_prompt(findings, csv_path, top_n)

            # Configure options with custom tool
            options = ClaudeAgentOptions(
                system_prompt=self.get_system_prompt(),
                max_turns=100,  # High limit for analyzing many findings
                allowed_tools=["mcp__triage__submit_triage_results"],
                mcp_servers={"triage": server},
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
            if _triage_results is None:
                raise AgentError("Agent did not call submit_triage_results tool")

            # Convert to TriageResult objects
            triage_results = self._parse_triage_results(_triage_results)

            # Sort by priority score (highest first)
            triage_results.sort(key=lambda x: x.priority_score, reverse=True)

            logger.info(
                "triage_completed",
                agent=self.agent_name,
                prioritized_count=len(triage_results),
                recommended_count=sum(1 for t in triage_results if t.recommended_for_analysis),
            )

            return triage_results

        except Exception as e:
            logger.error(
                "triage_failed",
                agent=self.agent_name,
                error=str(e),
            )
            raise AgentError(f"Triage failed: {e}") from e

    def _build_triage_prompt(
        self, findings: list[Finding], csv_path: Path | None, top_n: int
    ) -> str:
        """
        Build prompt for triage analysis.

        Args:
            findings: All findings to triage
            csv_path: Optional CSV path (not used yet, for future)
            top_n: Number of findings to prioritize

        Returns:
            Triage prompt
        """
        # Summarize findings for the prompt (don't include all details)
        findings_summary = []
        for finding in findings[:100]:  # Limit to first 100 for prompt size
            findings_summary.append({
                "id": finding.id,
                "rule_id": finding.rule_id,
                "severity": finding.severity.value,
                "location": finding.location,
                "message": finding.message[:100],  # Truncate long messages
            })

        findings_text = json.dumps(findings_summary, indent=2)

        if len(findings) > 100:
            additional_info = f"\n\nNote: Showing first 100 of {len(findings)} total findings. Focus prioritization on these."
        else:
            additional_info = ""

        return f"""Triage these security findings and identify the top {top_n} that need detailed investigation.

Total findings: {len(findings)}

Findings to analyze:
```json
{findings_text}
```{additional_info}

Steps:
1. Analyze the findings by severity, type, and context
2. Identify patterns and critical vulnerabilities
3. Select top {top_n} findings for detailed analysis
4. For each, assign a priority score (0.0-1.0) and provide reasoning
5. Call submit_triage_results tool with your prioritized list

Remember: Focus on findings with highest risk and clearest exploitation paths."""

    def _parse_triage_results(self, results: list[dict]) -> list[TriageResult]:
        """
        Parse tool results into TriageResult objects.

        Args:
            results: List of triage result dicts from tool

        Returns:
            List of TriageResult objects

        Raises:
            AgentError: If parsing fails
        """
        try:
            triage_results: list[TriageResult] = []

            for item in results:
                if not isinstance(item, dict):
                    logger.warning("triage_invalid_item", item=item)
                    continue

                # Validate required fields
                required = ["finding_id", "priority_score", "reasoning", "recommended_for_analysis"]
                if not all(field in item for field in required):
                    logger.warning("triage_missing_fields", item=item)
                    continue

                # Create TriageResult object
                triage_result = TriageResult(
                    finding_id=item["finding_id"],
                    priority_score=float(item["priority_score"]),
                    reasoning=item["reasoning"],
                    recommended_for_analysis=bool(item["recommended_for_analysis"]),
                )
                triage_results.append(triage_result)

            return triage_results

        except Exception as e:
            logger.error("triage_parse_error", error=str(e))
            raise AgentError(f"Failed to parse triage results: {e}") from e
