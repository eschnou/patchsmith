"""Fix generator agent for creating security patches."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.finding import Finding
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


class Fix(BaseModel):
    """A proposed fix for a security finding."""

    finding_id: str = Field(..., description="ID of the finding being fixed")
    file_path: Path = Field(..., description="File to be modified")
    original_code: str = Field(..., description="Original vulnerable code")
    fixed_code: str = Field(..., description="Fixed code")
    explanation: str = Field(..., description="Explanation of the fix")
    confidence: float = Field(
        ..., description="Confidence in the fix (0.0-1.0)", ge=0.0, le=1.0
    )


class FixGeneratorAgent(BaseAgent):
    """Agent for generating security vulnerability fixes using Claude AI.

    This agent analyzes vulnerable code and generates patches with explanations,
    ensuring fixes are safe and don't introduce new issues.
    """

    def get_system_prompt(self) -> str:
        """Get system prompt for fix generation."""
        return """You are a security-focused software engineer specializing in vulnerability remediation.

Your expertise includes:
- Understanding common vulnerability patterns (SQL injection, XSS, etc.)
- Writing secure code following best practices
- Language-specific security libraries and frameworks
- Minimal, focused fixes that don't break functionality
- Defensive programming techniques

When generating fixes:
1. Analyze the vulnerable code in full context
2. Identify the root cause of the vulnerability
3. Propose a minimal fix that addresses the issue
4. Preserve existing functionality and code style
5. Use secure coding patterns and libraries
6. Explain the fix clearly

Always respond with ONLY a JSON object in this exact format:
{
  "original_code": "The exact vulnerable code to replace",
  "fixed_code": "The secure replacement code",
  "explanation": "Clear explanation of what was changed and why",
  "confidence": 0.9
}

Requirements:
- original_code: Exact code snippet to be replaced (must match source file)
- fixed_code: Secure replacement (maintain formatting and style)
- explanation: Technical explanation for developers
- confidence: Float 0.0-1.0 (how confident you are the fix is correct)

Only suggest fixes you're confident are correct and won't break functionality."""

    async def execute(  # type: ignore[override]
        self,
        finding: Finding,
        context_lines: int = 10,
    ) -> Fix | None:
        """
        Generate a fix for a security finding.

        Args:
            finding: Finding to generate a fix for
            context_lines: Number of context lines to include around the vulnerability

        Returns:
            Fix object if successful, None if no fix could be generated

        Raises:
            AgentError: If fix generation fails
        """
        logger.info(
            "fix_generation_started",
            agent=self.agent_name,
            finding_id=finding.id,
            rule_id=finding.rule_id,
        )

        try:
            # Build generation prompt
            prompt = self._build_generation_prompt(finding, context_lines)

            # Query Claude
            response = await self.query_claude(
                prompt=prompt,
                max_turns=3,  # May need discussion to clarify requirements
                allowed_tools=["Read"],  # Allow reading source files for context
            )

            # Parse response
            fix = self._parse_response(response, finding)

            if fix:
                logger.info(
                    "fix_generation_completed",
                    agent=self.agent_name,
                    finding_id=finding.id,
                    confidence=fix.confidence,
                )
            else:
                logger.warning(
                    "fix_generation_no_fix",
                    agent=self.agent_name,
                    finding_id=finding.id,
                )

            return fix

        except Exception as e:
            logger.error(
                "fix_generation_failed",
                agent=self.agent_name,
                finding_id=finding.id,
                error=str(e),
            )
            raise AgentError(f"Fix generation failed: {e}") from e

    def _build_generation_prompt(
        self,
        finding: Finding,
        context_lines: int,
    ) -> str:
        """
        Build prompt for fix generation.

        Args:
            finding: Finding to fix
            context_lines: Number of context lines

        Returns:
            Generation prompt
        """
        cwe_info = f" ({finding.cwe.id})" if finding.cwe else ""
        snippet_info = f"\n\nVulnerable code:\n```\n{finding.snippet}\n```" if finding.snippet else ""

        return f"""Generate a security fix for this vulnerability.

Finding details:
- Rule: {finding.rule_id}
- Severity: {finding.severity.value.upper()}{cwe_info}
- Message: {finding.message}
- Location: {finding.location}{snippet_info}

Use the Read tool to examine the source file at {finding.file_path} around line {finding.start_line}.
Read {context_lines} lines before and after for full context.

Analyze the vulnerability and propose a secure fix as a JSON object.
If you cannot generate a safe fix with high confidence, explain why in the explanation field and set confidence to 0.0."""

    def _parse_response(self, response: str, finding: Finding) -> Fix | None:
        """
        Parse Claude's response into a Fix object.

        Args:
            response: Claude's response text
            finding: Original finding

        Returns:
            Fix object if parsing successful, None otherwise

        Raises:
            AgentError: If parsing fails
        """
        try:
            # Find JSON in response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                logger.warning(
                    "fix_parse_no_json",
                    finding_id=finding.id,
                    response_preview=response[:200],
                )
                return None

            json_str = response[json_start:json_end]
            data = json.loads(json_str)

            if not isinstance(data, dict):
                logger.warning(
                    "fix_parse_not_object",
                    finding_id=finding.id,
                )
                return None

            # Check for low confidence (no fix)
            confidence = float(data.get("confidence", 0.0))
            if confidence < 0.5:
                logger.info(
                    "fix_low_confidence",
                    finding_id=finding.id,
                    confidence=confidence,
                    explanation=data.get("explanation", "Unknown"),
                )
                return None

            # Validate required fields
            required = ["original_code", "fixed_code", "explanation", "confidence"]
            if not all(field in data for field in required):
                logger.warning(
                    "fix_parse_missing_fields",
                    finding_id=finding.id,
                    missing=[f for f in required if f not in data],
                )
                return None

            # Create Fix object
            return Fix(
                finding_id=finding.id,
                file_path=finding.file_path,
                original_code=str(data["original_code"]),
                fixed_code=str(data["fixed_code"]),
                explanation=str(data["explanation"]),
                confidence=confidence,
            )

        except json.JSONDecodeError as e:
            logger.warning(
                "fix_parse_json_error",
                finding_id=finding.id,
                error=str(e),
                response_preview=response[:200],
            )
            return None
        except Exception as e:
            logger.error(
                "fix_parse_error",
                finding_id=finding.id,
                error=str(e),
            )
            raise AgentError(f"Failed to parse fix response: {e}") from e
