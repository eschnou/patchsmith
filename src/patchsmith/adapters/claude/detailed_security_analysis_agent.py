"""Detailed security analysis agent for comprehensive finding assessment."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server, tool

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.finding import DetailedSecurityAssessment, Finding, RiskType
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


# Storage for tool results (per finding analysis)
_detailed_assessment: dict | None = None


@tool(
    "submit_detailed_assessment",
    "Submit comprehensive security assessment for a finding",
    {
        "is_false_positive": bool,
        "false_positive_score": float,  # 0.0-1.0
        "false_positive_reasoning": str,
        "attack_scenario": str,
        "risk_type": str,  # external_pentest, internal_abuse, supply_chain, configuration, data_exposure, other
        "exploitability_score": float,  # 0.0-1.0
        "impact_description": str,
        "remediation_priority": str,  # immediate, high, medium, low
    },
)
async def submit_detailed_assessment_tool(args: dict) -> dict:
    """Tool for submitting detailed security assessment."""
    global _detailed_assessment

    # Handle JSON string input
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            logger.error("submit_detailed_assessment_invalid_json", data=str(args)[:200])
            return {
                "content": [
                    {"type": "text", "text": "Error: Invalid JSON format"}
                ]
            }

    _detailed_assessment = {
        "is_false_positive": args.get("is_false_positive", False),
        "false_positive_score": float(args.get("false_positive_score", 0.0)),
        "false_positive_reasoning": args.get("false_positive_reasoning", ""),
        "attack_scenario": args.get("attack_scenario", ""),
        "risk_type": args.get("risk_type", "other"),
        "exploitability_score": float(args.get("exploitability_score", 0.0)),
        "impact_description": args.get("impact_description", ""),
        "remediation_priority": args.get("remediation_priority", "medium"),
    }

    logger.info(
        "detailed_assessment_submitted",
        is_false_positive=_detailed_assessment["is_false_positive"],
        risk_type=_detailed_assessment["risk_type"],
        exploitability=_detailed_assessment["exploitability_score"],
        priority=_detailed_assessment["remediation_priority"],
    )

    return {
        "content": [
            {
                "type": "text",
                "text": f"Assessment recorded: {'FALSE POSITIVE' if _detailed_assessment['is_false_positive'] else 'VALID'} | Risk: {_detailed_assessment['risk_type']} | Priority: {_detailed_assessment['remediation_priority']}",
            }
        ]
    }


class DetailedSecurityAnalysisAgent(BaseAgent):
    """Agent for comprehensive security analysis of findings.

    This agent performs deep analysis of security findings, going beyond simple
    false positive detection to provide:
    - False positive assessment
    - Attack scenario description
    - Risk classification
    - Exploitability analysis
    - Impact assessment
    - Remediation prioritization
    """

    def get_system_prompt(self) -> str:
        """Get system prompt for detailed security analysis."""
        return """You are an expert security analyst conducting comprehensive vulnerability assessments.

Your expertise includes:
- Penetration testing and red team operations
- Understanding attack scenarios and exploitation techniques
- Risk classification and impact analysis
- Code analysis and vulnerability validation
- Remediation prioritization

When analyzing findings, you must assess:

1. **False Positive Analysis**
   - Is this a legitimate vulnerability or false alarm?
   - Consider input validation, sanitization, security controls
   - Check for framework protections and context-specific mitigations

2. **Attack Scenario**
   - How would an attacker exploit this vulnerability?
   - What are the exploitation steps?
   - What attacker capabilities are required?

3. **Risk Type Classification**
   - external_pentest: Exploitable from external network/internet
   - internal_abuse: Requires internal access or authenticated user
   - supply_chain: Related to dependencies or build process
   - configuration: Security misconfiguration
   - data_exposure: Sensitive data leak or exposure
   - other: Other security concerns

4. **Exploitability**
   - How difficult is this to exploit? (0.0 = very hard, 1.0 = trivial)
   - Consider: access requirements, technical complexity, reliability

5. **Impact**
   - What happens if successfully exploited?
   - Consider: data breach, system compromise, service disruption

6. **Remediation Priority**
   - immediate: Critical issue requiring immediate action
   - high: Should be fixed in current sprint
   - medium: Fix in next sprint or release
   - low: Address when convenient

You have access to:
- Read: Examine source files to understand code context
- submit_detailed_assessment: Submit your comprehensive analysis (YOU MUST call this)

Process:
1. Use Read tool to examine the vulnerable code and surrounding context
2. Analyze the vulnerability thoroughly
3. Develop attack scenario
4. Assess false positive likelihood, exploitability, and impact
5. Classify risk type and set remediation priority
6. Call submit_detailed_assessment tool with your complete analysis

The submit_detailed_assessment tool expects all fields. Be specific and technical.

YOU MUST call the submit_detailed_assessment tool to report your analysis."""

    async def execute(  # type: ignore[override]
        self,
        findings: list[Finding],
    ) -> dict[str, DetailedSecurityAssessment]:
        """
        Perform detailed security analysis on findings.

        Args:
            findings: List of findings to analyze (typically pre-triaged top N)

        Returns:
            Dictionary mapping finding_id to DetailedSecurityAssessment

        Raises:
            AgentError: If analysis fails
        """
        logger.info(
            "detailed_analysis_started",
            agent=self.agent_name,
            finding_count=len(findings),
        )

        try:
            assessments: dict[str, DetailedSecurityAssessment] = {}

            # Create MCP server with custom tool
            server = create_sdk_mcp_server(
                name="detailed-analysis",
                version="1.0.0",
                tools=[submit_detailed_assessment_tool],
            )

            for finding in findings:
                global _detailed_assessment
                _detailed_assessment = None  # Reset for each finding

                try:
                    # Build analysis prompt
                    prompt = self._build_analysis_prompt(finding)

                    # Configure options with custom tool
                    options = ClaudeAgentOptions(
                        system_prompt=self.get_system_prompt(),
                        max_turns=100,  # High limit for thorough analysis
                        allowed_tools=["Read", "mcp__detailed-analysis__submit_detailed_assessment"],
                        mcp_servers={"detailed-analysis": server},
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
                                finding_id=finding.id,
                            )

                            # Check for tool use
                            if message_type == "AssistantMessage" and hasattr(message, "content"):
                                for item in message.content if isinstance(message.content, list) else []:
                                    if hasattr(item, "type") and item.type == "tool_use":
                                        logger.info(
                                            "tool_use_detected",
                                            agent=self.agent_name,
                                            finding_id=finding.id,
                                            tool_name=getattr(item, "name", "unknown"),
                                        )

                            # Log final result
                            if message_type == "ResultMessage":
                                logger.info(
                                    "result_message_received",
                                    agent=self.agent_name,
                                    finding_id=finding.id,
                                    subtype=getattr(message, "subtype", "unknown"),
                                    num_turns=getattr(message, "num_turns", 0),
                                )

                    # Check if tool was called
                    if _detailed_assessment is None:
                        logger.warning(
                            "finding_analysis_no_result",
                            finding_id=finding.id,
                        )
                        continue

                    # Create DetailedSecurityAssessment from result
                    assessment = DetailedSecurityAssessment(
                        finding_id=finding.id,
                        is_false_positive=_detailed_assessment["is_false_positive"],
                        false_positive_score=_detailed_assessment["false_positive_score"],
                        false_positive_reasoning=_detailed_assessment["false_positive_reasoning"],
                        attack_scenario=_detailed_assessment["attack_scenario"],
                        risk_type=RiskType(_detailed_assessment["risk_type"]),
                        exploitability_score=_detailed_assessment["exploitability_score"],
                        impact_description=_detailed_assessment["impact_description"],
                        remediation_priority=_detailed_assessment["remediation_priority"],
                    )
                    assessments[finding.id] = assessment

                    logger.debug(
                        "finding_analyzed",
                        finding_id=finding.id,
                        is_false_positive=assessment.is_false_positive,
                        risk_type=assessment.risk_type.value,
                        priority=assessment.remediation_priority,
                    )

                except Exception as e:
                    logger.warning(
                        "finding_analysis_failed",
                        finding_id=finding.id,
                        error=str(e),
                    )
                    # Skip this finding but continue with others

            logger.info(
                "detailed_analysis_completed",
                agent=self.agent_name,
                analyzed=len(assessments),
                false_positives=sum(1 for a in assessments.values() if a.is_false_positive),
            )

            return assessments

        except Exception as e:
            logger.error(
                "detailed_analysis_error",
                agent=self.agent_name,
                error=str(e),
            )
            raise AgentError(f"Detailed security analysis failed: {e}") from e

    def _build_analysis_prompt(self, finding: Finding) -> str:
        """
        Build prompt for analyzing a specific finding.

        Args:
            finding: Finding to analyze

        Returns:
            Analysis prompt
        """
        cwe_info = f" ({finding.cwe.id})" if finding.cwe else ""
        snippet_info = f"\n\nCode snippet:\n```\n{finding.snippet}\n```" if finding.snippet else ""

        return f"""Perform comprehensive security analysis on this finding.

Finding details:
- ID: {finding.id}
- Rule: {finding.rule_id}
- Severity: {finding.severity.value.upper()}{cwe_info}
- Location: {finding.location}
- Message: {finding.message}{snippet_info}

Steps:
1. Use Read tool to examine {finding.file_path} for full context
2. Analyze if this is a false positive or legitimate vulnerability
3. If legitimate, develop a detailed attack scenario
4. Classify the risk type (external_pentest, internal_abuse, etc.)
5. Assess exploitability (0.0-1.0)
6. Describe the potential impact
7. Set remediation priority (immediate, high, medium, low)
8. Call submit_detailed_assessment tool with your complete analysis

Be thorough and specific. Provide technical details in your assessment.

Remember: You MUST use the submit_detailed_assessment tool to report your results."""
