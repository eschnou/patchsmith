"""Fix generator agent for creating security patches."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server, tool
from pydantic import BaseModel, Field

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.finding import Finding
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger()


# Storage for tool results
_fix_proposal: dict | None = None


@tool(
    "submit_fix_proposal",
    "Submit a proposed security fix for a vulnerability",
    {
        "original_code": str,  # Exact vulnerable code to replace
        "fixed_code": str,  # Secure replacement code
        "explanation": str,  # Clear explanation of the fix
        "confidence": float,  # 0.0-1.0 confidence score
    },
)
async def submit_fix_proposal_tool(args: dict) -> dict:
    """Tool for submitting fix proposals."""
    global _fix_proposal

    # Handle JSON string input
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            logger.error("submit_fix_proposal_invalid_json", data=str(args)[:200])
            return {
                "content": [
                    {"type": "text", "text": "Error: Invalid JSON format"}
                ]
            }

    _fix_proposal = {
        "original_code": args.get("original_code", ""),
        "fixed_code": args.get("fixed_code", ""),
        "explanation": args.get("explanation", ""),
        "confidence": float(args.get("confidence", 0.0)),
    }

    logger.info(
        "fix_proposal_submitted",
        confidence=_fix_proposal["confidence"],
        has_original=len(_fix_proposal["original_code"]) > 0,
        has_fixed=len(_fix_proposal["fixed_code"]) > 0,
    )

    return {
        "content": [
            {
                "type": "text",
                "text": f"Fix proposal recorded with confidence {_fix_proposal['confidence']:.2f}",
            }
        ]
    }


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

    This agent analyzes vulnerable code and generates patches with explanations.
    It does NOT apply fixes - that's the responsibility of the calling code.
    The agent only has Read access to examine code, not Write/Git access.
    """

    def get_system_prompt(self) -> str:
        """Get system prompt for fix generation."""
        return """You are a security-focused software engineer specializing in vulnerability remediation.

Your expertise includes:
- Understanding common vulnerability patterns (SQL injection, XSS, CSRF, etc.)
- Writing secure code following best practices
- Language-specific security libraries and frameworks
- Minimal, focused fixes that don't break functionality
- Defensive programming techniques

When generating fixes:
1. Use Read tool to examine the vulnerable code in full context
2. Identify the root cause of the vulnerability
3. Propose a minimal fix that addresses the security issue
4. Preserve existing functionality, code style, and formatting
5. Use secure coding patterns and language-specific security libraries
6. Provide clear technical explanation

You have access to:
- Read: Examine source files to understand code context
- submit_fix_proposal: Submit your fix proposal (YOU MUST call this)

Process:
1. Use Read tool to examine the source file around the vulnerability
2. Analyze the vulnerable code pattern
3. Design a secure fix that addresses the root cause
4. Ensure the fix is minimal and maintains functionality
5. Call submit_fix_proposal tool with your fix

The submit_fix_proposal tool expects:
{
  "original_code": "def vulnerable():\\n    query = \\"SELECT * WHERE id=\\" + user_input",
  "fixed_code": "def secure():\\n    query = \\"SELECT * WHERE id=?\\"\\n    cursor.execute(query, (user_input,))",
  "explanation": "Replaced string concatenation with parameterized query to prevent SQL injection",
  "confidence": 0.95
}

Requirements:
- original_code: Exact code snippet to replace (must match source file exactly)
- fixed_code: Secure replacement (maintain indentation and style)
- explanation: Technical explanation for developers
- confidence: 0.0-1.0 (only suggest fixes you're confident are correct)

If you cannot generate a safe fix with high confidence (>0.7), set confidence low and explain why in the explanation.

YOU MUST call the submit_fix_proposal tool to report your fix."""

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
            Fix object if successful (confidence >0.7), None if no fix could be generated

        Raises:
            AgentError: If fix generation fails
        """
        global _fix_proposal
        _fix_proposal = None  # Reset

        logger.info(
            "fix_generation_started",
            agent=self.agent_name,
            finding_id=finding.id,
            rule_id=finding.rule_id,
        )

        try:
            # Create MCP server with custom tool
            server = create_sdk_mcp_server(
                name="fix-generator",
                version="1.0.0",
                tools=[submit_fix_proposal_tool],
            )

            # Build generation prompt
            prompt = self._build_generation_prompt(finding, context_lines)

            # Configure options with custom tool
            options = ClaudeAgentOptions(
                system_prompt=self.get_system_prompt(),
                max_turns=100,  # High limit for thorough analysis
                allowed_tools=["Read", "mcp__fix-generator__submit_fix_proposal"],
                mcp_servers={"fix-generator": server},
                cwd=str(self.working_dir),
            )

            # Query Claude with custom client
            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                async for message in client.receive_response():
                    message_type = type(message).__name__

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
            if _fix_proposal is None:
                logger.warning(
                    "fix_generation_no_proposal",
                    agent=self.agent_name,
                    finding_id=finding.id,
                )
                return None

            # Check confidence threshold
            if _fix_proposal["confidence"] < 0.7:
                logger.info(
                    "fix_generation_low_confidence",
                    agent=self.agent_name,
                    finding_id=finding.id,
                    confidence=_fix_proposal["confidence"],
                    explanation=_fix_proposal["explanation"][:100],
                )
                return None

            # Create Fix object
            fix = Fix(
                finding_id=finding.id,
                file_path=finding.file_path,
                original_code=_fix_proposal["original_code"],
                fixed_code=_fix_proposal["fixed_code"],
                explanation=_fix_proposal["explanation"],
                confidence=_fix_proposal["confidence"],
            )

            logger.info(
                "fix_generation_completed",
                agent=self.agent_name,
                finding_id=finding.id,
                confidence=fix.confidence,
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
        snippet_info = f"\n\nVulnerable code snippet:\n```\n{finding.snippet}\n```" if finding.snippet else ""

        return f"""Generate a security fix for this vulnerability.

Finding details:
- ID: {finding.id}
- Rule: {finding.rule_id}
- Severity: {finding.severity.value.upper()}{cwe_info}
- Message: {finding.message}
- Location: {finding.location}{snippet_info}

Steps:
1. Use Read tool to examine {finding.file_path} around line {finding.start_line}
   (read at least {context_lines} lines before/after for full context)
2. Analyze the vulnerability pattern
3. Design a secure fix that addresses the root cause
4. Ensure the fix is minimal and maintains existing functionality
5. Call submit_fix_proposal tool with your fix

Important:
- original_code must EXACTLY match the code in the source file (including whitespace)
- fixed_code should maintain the same indentation and code style
- Only propose fixes you're confident are correct and safe (confidence >0.7)
- If uncertain, explain why and set confidence low

Remember: You MUST use the submit_fix_proposal tool to report your fix."""
