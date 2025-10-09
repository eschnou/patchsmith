"""Triage agent for prioritizing security findings."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server, tool

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.analysis import TriageResult
from patchsmith.models.finding import Finding
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


class TriageAgent(BaseAgent):
    """Agent for triaging and prioritizing security findings.

    This agent analyzes all findings at a high level to identify the most
    critical issues that warrant detailed investigation. It considers severity,
    vulnerability type, context, and potential impact to create a prioritized list.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize triage agent with result storage."""
        super().__init__(*args, **kwargs)
        self._triage_results: list[dict] | None = None

    def _create_submit_tool(self) -> Any:
        """Create submit_triage_results tool with closure to access instance state.

        Returns:
            Tool function that can access self._triage_results
        """
        # Capture self in closure
        agent_instance = self

        @tool(
            "submit_triage_results",
            "Submit prioritized findings after triage analysis",
            {
                "prioritized_findings": list,  # List of {finding_id: str, priority_score: float, reasoning: str, recommended_for_analysis: bool}
            },
        )
        async def submit_triage_results_tool(args: dict) -> dict:
            """Tool for submitting triage results."""
            # Handle JSON string input
            prioritized = args.get("prioritized_findings", [])
            if isinstance(prioritized, str):
                try:
                    prioritized = json.loads(prioritized)
                except json.JSONDecodeError:
                    logger.error("submit_triage_invalid_json", data=str(prioritized)[:200])
                    return {"content": [{"type": "text", "text": "Error: Invalid JSON format"}]}

            # Store in instance variable instead of global
            agent_instance._triage_results = prioritized

            recommended_count = sum(
                1 for item in prioritized if item.get("recommended_for_analysis", False)
            )

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

        return submit_triage_results_tool

    def get_system_prompt(self) -> str:
        """Get system prompt for triage."""
        return """You are a security triage expert who prioritizes vulnerabilities for investigation.

Your expertise includes:
- Risk assessment and prioritization
- Understanding vulnerability criticality
- Identifying patterns in security findings
- Balancing severity, exploitability, and impact
- Recognizing common false positive patterns
- Grouping similar findings to avoid redundant investigations

When triaging findings, consider:
- Severity level (critical > high > medium > low)
- Vulnerability type (SQL injection, XSS, etc.)
- Location and context (production code vs tests, public-facing vs internal)
- Potential impact and exploitability
- Likelihood of being a false positive
- Patterns across multiple findings

**IMPORTANT - Finding Grouping:**
If multiple findings share the same vulnerability pattern (e.g., "5 instances of missing-await in wallet.ts"), you should GROUP them to avoid redundant AI investigations:

1. Identify findings with the same rule_id and similar contexts (same file, same function, same pattern)
2. Select ONE representative finding (typically the first one or most critical example)
3. In the representative's entry, include:
   - related_finding_ids: list of all OTHER finding IDs in the group (not including the representative)
   - group_pattern: descriptive label (e.g., "Missing await in wallet.ts functions")
4. **CRITICAL**: Return ONLY the representative, NOT the related instances as separate entries

**Grouping Example:**
If you find F-20, F-21, F-22, F-23, F-24, F-25 are all "missing-await in wallet.ts":
- Return ONLY F-20 as the representative
- Set F-20's related_finding_ids = ["F-21", "F-22", "F-23", "F-24", "F-25"]
- Do NOT return F-21 through F-25 as separate entries

Example of grouped finding:
{
  "finding_id": "F-3",  // representative
  "priority_score": 0.85,
  "reasoning": "Missing await pattern on isSessionOpen found in 5 locations",
  "recommended_for_analysis": true,
  "related_finding_ids": ["F-1", "F-2", "F-4", "F-5"],  // other instances
  "group_pattern": "Missing await on isSessionOpen"
}

You have access to:
- submit_triage_results: Submit your prioritization (YOU MUST call this with your results)

Process:
1. Review all findings provided in the prompt
2. Identify patterns and group similar findings (same rule_id AND similar context)
3. For each group, select ONE representative finding - do NOT return the others
4. Assign priority scores (0.0-1.0) to all groups/individual findings
5. Mark top priority findings/groups for detailed investigation (you'll be told how many)
6. Provide reasoning for all entries, especially high-priority ones
7. Call submit_triage_results tool with all DISTINCT groups/findings

**IMPORTANT**:
- Return one entry per DISTINCT vulnerability pattern (not per raw finding)
- If 6 findings share the same pattern → return 1 entry (representative) with related_finding_ids containing the other 5
- If a finding is unique → return it as a standalone entry with empty related_finding_ids
- The number of entries you return = number of distinct patterns/groups, NOT the total raw finding count
- Mark the top N groups/findings as `recommended_for_analysis: true`, rest as `false`

The submit_triage_results tool expects:
{
  "prioritized_findings": [
    {
      "finding_id": "sql-injection_app.py_42",
      "priority_score": 0.95,
      "reasoning": "Critical SQL injection in authentication code with user input",
      "recommended_for_analysis": true,
      "related_finding_ids": [],  // Optional: other findings in group
      "group_pattern": null  // Optional: pattern description
    },
    ...
  ]
}

Requirements (for EACH finding):
- finding_id: exact ID from the findings list (representative)
- priority_score: float 0.0-1.0 (higher = more critical)
- reasoning: brief explanation (1-2 sentences, mention if grouped)
- recommended_for_analysis: true for top priority findings, false for others
- related_finding_ids: (optional) list of other finding IDs in the same group
- group_pattern: (optional) description of the common pattern

When setting `recommended_for_analysis`:
- Mark the TOP priority findings/groups as `true` (you'll be told how many in the prompt)
- These will receive detailed AI security analysis
- All others should be `false`
- But ALL findings must be returned with scores and grouping

Prioritization criteria for top findings:
- Highest severity with clear exploitation paths
- Vulnerabilities in critical code paths
- Issues with significant potential impact
- Findings that are unlikely to be false positives
- Group similar findings throughout ALL findings to reduce redundancy

YOU MUST call the submit_triage_results tool with ALL findings triaged."""

    async def execute(  # type: ignore[override]
        self,
        findings: list[Finding],
        csv_path: Path | None = None,
        top_n: int = 10,
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
        # Reset instance results
        self._triage_results = None

        logger.info(
            "triage_started",
            agent=self.agent_name,
            total_findings=len(findings),
            top_n=top_n,
        )

        try:
            # Create MCP server with custom tool (using instance method)
            submit_tool = self._create_submit_tool()
            server = create_sdk_mcp_server(
                name="triage",
                version="1.0.0",
                tools=[submit_tool],
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
            if self._triage_results is None:
                raise AgentError("Agent did not call submit_triage_results tool")

            # Convert to TriageResult objects
            triage_results = self._parse_triage_results(self._triage_results)

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
            findings_summary.append(
                {
                    "id": finding.id,
                    "rule_id": finding.rule_id,
                    "severity": finding.severity.value,
                    "location": finding.location,
                    "message": finding.message[:500],  # Truncate long messages
                }
            )

        findings_text = json.dumps(findings_summary, indent=2)

        if len(findings) > 100:
            additional_info = f"\n\nNote: Showing first 100 of {len(findings)} total findings. Focus prioritization on these."
        else:
            additional_info = ""

        return f"""Triage security findings and identify distinct vulnerability patterns.

Total raw findings: {len(findings)}

Findings to analyze:
```json
{findings_text}
```{additional_info}

Steps:
1. Review all findings by severity, type, location, and context
2. **Group similar findings**: If multiple findings share the same rule_id AND similar context (same file, same function, same pattern), group them into ONE entry
3. For each group, select ONE representative (do not include related instances as separate entries)
4. Assign priority scores (0.0-1.0) to each distinct group/finding
5. Mark the top {top_n} highest priority groups with `recommended_for_analysis: true`
6. Mark all other groups with `recommended_for_analysis: false`
7. Call submit_triage_results with all DISTINCT groups/patterns (NOT all raw findings)

**CRITICAL GROUPING RULES**:
- Same rule_id + same file + similar pattern = GROUP them (e.g., 6× "missing-await" in wallet.ts → 1 entry)
- Same rule_id + different files = SEPARATE entries (different contexts)
- Different rule_ids = SEPARATE entries (different vulnerability types)
- Return COUNT = number of distinct patterns, NOT raw finding count

**Example**: If you see:
- F-20, F-21, F-22, F-23, F-24, F-25: all "js/missing-await" in wallet.ts
- Return ONLY F-20 with related_finding_ids = ["F-21", "F-22", "F-23", "F-24", "F-25"]
- Do NOT return F-21 through F-25 as separate entries

Your goal: Return {top_n} highly prioritized groups + all other distinct groups (not recommended), with proper grouping to avoid redundant investigations."""

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

                # Extract optional grouping fields
                related_ids = item.get("related_finding_ids", [])
                if not isinstance(related_ids, list):
                    related_ids = []

                group_pattern = item.get("group_pattern")
                if group_pattern == "null" or group_pattern == "":
                    group_pattern = None

                # Create TriageResult object
                triage_result = TriageResult(
                    finding_id=item["finding_id"],
                    priority_score=float(item["priority_score"]),
                    reasoning=item["reasoning"],
                    recommended_for_analysis=bool(item["recommended_for_analysis"]),
                    related_finding_ids=related_ids,
                    group_pattern=group_pattern,
                )
                triage_results.append(triage_result)

            return triage_results

        except Exception as e:
            logger.error("triage_parse_error", error=str(e))
            raise AgentError(f"Failed to parse triage results: {e}") from e
