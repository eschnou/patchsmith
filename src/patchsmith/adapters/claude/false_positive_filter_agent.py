"""False positive filter agent for assessing finding validity."""

import json
from typing import TYPE_CHECKING

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.finding import FalsePositiveScore, Finding
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


class FalsePositiveFilterAgent(BaseAgent):
    """Agent for filtering false positives from security findings using Claude AI.

    This agent analyzes code context around findings to determine if they are
    likely to be false positives, providing confidence scores and reasoning.
    """

    def get_system_prompt(self) -> str:
        """Get system prompt for false positive analysis."""
        return """You are a security analysis expert specializing in false positive detection.

Your expertise includes:
- Understanding code context and control flow
- Identifying legitimate security vulnerabilities vs false alarms
- Recognizing sanitization patterns and security controls
- Evaluating data flow and taint analysis results

When analyzing findings, consider:
- Input validation and sanitization
- Security controls and guards
- Context-specific mitigations
- Framework-specific protections
- Dead code or unreachable paths

Always respond with ONLY a JSON object in this exact format:
{
  "is_false_positive": true,
  "score": 0.85,
  "reasoning": "Detailed explanation of why this is/isn't a false positive"
}

Requirements:
- is_false_positive: boolean (true if likely false positive)
- score: float 0.0-1.0 (confidence in the assessment)
- reasoning: string explaining the decision with specific evidence

Be thorough and accurate. High scores require clear evidence."""

    async def execute(  # type: ignore[override]
        self,
        findings: list[Finding],
        max_concurrent: int = 5,
    ) -> list[Finding]:
        """
        Analyze findings and update with false positive scores.

        Args:
            findings: List of findings to analyze
            max_concurrent: Maximum concurrent analyses (for rate limiting)

        Returns:
            List of findings with false positive scores added

        Raises:
            AgentError: If analysis fails
        """
        logger.info(
            "false_positive_analysis_started",
            agent=self.agent_name,
            finding_count=len(findings),
        )

        try:
            analyzed_findings: list[Finding] = []

            for finding in findings:
                try:
                    # Analyze individual finding
                    prompt = self._build_analysis_prompt(finding)

                    response = await self.query_claude(
                        prompt=prompt,
                        max_turns=2,
                        allowed_tools=["Read"],  # Allow reading source files
                    )

                    # Parse response and update finding
                    fp_score = self._parse_response(response)

                    # Create updated finding with FP score
                    updated_finding = Finding(
                        id=finding.id,
                        rule_id=finding.rule_id,
                        message=finding.message,
                        severity=finding.severity,
                        file_path=finding.file_path,
                        start_line=finding.start_line,
                        end_line=finding.end_line,
                        cwe=finding.cwe,
                        snippet=finding.snippet,
                        false_positive_score=fp_score,
                    )
                    analyzed_findings.append(updated_finding)

                    logger.debug(
                        "finding_analyzed",
                        finding_id=finding.id,
                        is_false_positive=fp_score.is_false_positive,
                        score=fp_score.score,
                    )

                except Exception as e:
                    logger.warning(
                        "finding_analysis_failed",
                        finding_id=finding.id,
                        error=str(e),
                    )
                    # Keep original finding without FP score
                    analyzed_findings.append(finding)

            logger.info(
                "false_positive_analysis_completed",
                agent=self.agent_name,
                analyzed=len(analyzed_findings),
                false_positives=sum(
                    1 for f in analyzed_findings
                    if f.false_positive_score and f.false_positive_score.is_false_positive
                ),
            )

            return analyzed_findings

        except Exception as e:
            logger.error(
                "false_positive_analysis_error",
                agent=self.agent_name,
                error=str(e),
            )
            raise AgentError(f"False positive analysis failed: {e}") from e

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

        return f"""Analyze this security finding to determine if it's a false positive.

Finding details:
- Rule: {finding.rule_id}
- Message: {finding.message}
- Severity: {finding.severity.value}{cwe_info}
- Location: {finding.file_path}:{finding.start_line}{snippet_info}

Use the Read tool to examine the full source file at {finding.file_path} for context.
Analyze the code flow, input validation, sanitization, and security controls.

Provide your assessment as a JSON object."""

    def _parse_response(self, response: str) -> FalsePositiveScore:
        """
        Parse Claude's response into a FalsePositiveScore.

        Args:
            response: Claude's response text

        Returns:
            FalsePositiveScore object

        Raises:
            AgentError: If parsing fails
        """
        try:
            # Find JSON in response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                raise AgentError("No JSON object found in response")

            json_str = response[json_start:json_end]
            data = json.loads(json_str)

            if not isinstance(data, dict):
                raise AgentError("Response is not a JSON object")

            # Validate required fields
            required = ["is_false_positive", "score", "reasoning"]
            if not all(field in data for field in required):
                raise AgentError(f"Missing required fields. Expected: {required}")

            # Create FalsePositiveScore
            return FalsePositiveScore(
                is_false_positive=bool(data["is_false_positive"]),
                score=float(data["score"]),
                reasoning=str(data["reasoning"]),
            )

        except json.JSONDecodeError as e:
            logger.error(
                "false_positive_parse_json_error",
                error=str(e),
                response=response[:200],
            )
            raise AgentError(f"Failed to parse JSON response: {e}") from e
        except Exception as e:
            logger.error(
                "false_positive_parse_error",
                error=str(e),
                response=response[:200],
            )
            raise AgentError(f"Failed to parse response: {e}") from e
