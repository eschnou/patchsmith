"""Autonomous fix agent that can write files to fix vulnerabilities."""

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


# Storage for agent results
_fix_result: dict | None = None


@tool(
    "complete_fix",
    "Signal that the fix is complete and validated",
    {
        "description": str,  # What was fixed
        "confidence": float,  # 0.0-1.0 confidence score
        "files_modified": list,  # List of file paths modified
    },
)
async def complete_fix_tool(args: dict) -> dict:
    """Tool for agent to signal fix completion."""
    global _fix_result

    # Handle JSON string input
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            logger.error("complete_fix_invalid_json", data=str(args)[:200])
            return {"content": [{"type": "text", "text": "Error: Invalid JSON format"}]}

    # Normalize files_modified to always be a list
    files_modified = args.get("files_modified", [])
    if isinstance(files_modified, str):
        # Agent passed a single string instead of a list
        files_modified = [files_modified]
    elif not isinstance(files_modified, list):
        # Convert any other type to list
        files_modified = list(files_modified) if files_modified else []

    _fix_result = {
        "success": True,
        "description": args.get("description", ""),
        "confidence": float(args.get("confidence", 0.0)),
        "files_modified": files_modified,
    }

    logger.info(
        "fix_completed",
        confidence=_fix_result["confidence"],
        files_count=len(_fix_result["files_modified"]),
    )

    return {
        "content": [
            {
                "type": "text",
                "text": f"Fix completion recorded. Files modified: {len(_fix_result['files_modified'])}, Confidence: {_fix_result['confidence']:.0%}",
            }
        ]
    }


@tool(
    "abandon_fix",
    "Signal that you cannot fix this vulnerability",
    {
        "reason": str,  # Why the fix cannot be completed
    },
)
async def abandon_fix_tool(args: dict) -> dict:
    """Tool for agent to signal it cannot complete the fix."""
    global _fix_result

    # Handle JSON string input
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            logger.error("abandon_fix_invalid_json", data=str(args)[:200])
            return {"content": [{"type": "text", "text": "Error: Invalid JSON format"}]}

    _fix_result = {
        "success": False,
        "reason": args.get("reason", "Unknown reason"),
    }

    logger.warning("fix_abandoned", reason=_fix_result["reason"])

    return {
        "content": [
            {
                "type": "text",
                "text": f"Acknowledged. Fix abandoned: {_fix_result['reason']}",
            }
        ]
    }


class FixResult(BaseModel):
    """Result of an autonomous fix operation."""

    success: bool = Field(..., description="Whether fix was completed")
    description: str = Field(default="", description="Description of what was fixed")
    confidence: float = Field(default=0.0, description="Confidence in fix (0.0-1.0)")
    files_modified: list[str] = Field(
        default_factory=list, description="List of files modified"
    )
    reason: str = Field(default="", description="Reason for failure if not successful")


class AutonomousFixAgent(BaseAgent):
    """Agent for autonomously fixing security vulnerabilities.

    This agent has Write access to directly modify source files to fix vulnerabilities.
    It works iteratively: examine code, write fix, validate by re-reading, complete.

    The agent does NOT have Bash access - it cannot run tests or builds.
    It relies on code analysis and best practices to create fixes.
    """

    def get_system_prompt(self) -> str:
        """Get system prompt for autonomous fixing."""
        return """You are an autonomous security fix engineer with direct file access.

Your mission: Fix security vulnerabilities by directly modifying source code.

Your expertise:
- Understanding vulnerability patterns (SQL injection, XSS, CSRF, etc.)
- Writing secure code following best practices
- Language-specific security libraries and frameworks
- Defensive programming techniques
- Code style preservation

Your capabilities:
- Read: Examine any source file to understand context
- Write: Directly modify files to implement fixes
- complete_fix: Signal when fix is validated and complete
- abandon_fix: Give up if fix is impossible

Your workflow:
1. Use Read to examine the vulnerable file and surrounding context
2. Analyze the vulnerability pattern and root cause
3. Plan a minimal, focused fix that preserves functionality
4. Use Write to apply the fix directly to file(s)
5. Use Read to verify your changes were applied correctly
6. Repeat steps 4-5 if you need to refine the fix
7. Call complete_fix when satisfied with the fix

Requirements:
- Preserve existing code style, indentation, and formatting
- Make minimal changes - only fix the security issue
- Maintain all existing functionality
- Use language-specific security best practices
- If you cannot fix safely, call abandon_fix with clear reasoning

Important notes:
- You do NOT have Bash access - cannot run tests or builds
- Rely on code analysis and security knowledge
- Be conservative - only make changes you're confident about
- If unsure, explain in abandon_fix rather than guessing

Example fix workflow:
1. Read vulnerable file
2. Write secure replacement
3. Read file again to verify changes
4. Call complete_fix with description and confidence

You MUST call either complete_fix or abandon_fix when done.
"""

    async def execute(  # type: ignore[override]
        self,
        finding: Finding,
    ) -> FixResult:
        """
        Autonomously fix a security vulnerability.

        Args:
            finding: Finding to fix

        Returns:
            FixResult indicating success/failure and details

        Raises:
            AgentError: If agent execution fails
        """
        global _fix_result
        _fix_result = None  # Reset

        logger.info(
            "autonomous_fix_started",
            agent=self.agent_name,
            finding_id=finding.id,
            rule_id=finding.rule_id,
        )

        try:
            # Create MCP server with custom tools
            server = create_sdk_mcp_server(
                name="autonomous-fix",
                version="1.0.0",
                tools=[complete_fix_tool, abandon_fix_tool],
            )

            # Build prompt
            prompt = self._build_fix_prompt(finding)

            # Configure options with Write access
            options = ClaudeAgentOptions(
                system_prompt=self.get_system_prompt(),
                max_turns=100,  # High limit for iterative fixing
                allowed_tools=[
                    "Read",
                    "Write",
                    "mcp__autonomous-fix__complete_fix",
                    "mcp__autonomous-fix__abandon_fix",
                ],
                mcp_servers={"autonomous-fix": server},
                cwd=str(self.working_dir),
            )

            # Run agent
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

                    # Log tool usage
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

            # Check if agent completed
            if _fix_result is None:
                logger.warning(
                    "autonomous_fix_no_completion",
                    agent=self.agent_name,
                    finding_id=finding.id,
                )
                return FixResult(
                    success=False,
                    reason="Agent did not call complete_fix or abandon_fix",
                )

            # Return result
            if _fix_result["success"]:
                logger.info(
                    "autonomous_fix_completed",
                    agent=self.agent_name,
                    finding_id=finding.id,
                    confidence=_fix_result["confidence"],
                    files_count=len(_fix_result["files_modified"]),
                )

                return FixResult(
                    success=True,
                    description=_fix_result["description"],
                    confidence=_fix_result["confidence"],
                    files_modified=_fix_result["files_modified"],
                )
            else:
                logger.warning(
                    "autonomous_fix_abandoned",
                    agent=self.agent_name,
                    finding_id=finding.id,
                    reason=_fix_result["reason"],
                )

                return FixResult(
                    success=False,
                    reason=_fix_result["reason"],
                )

        except Exception as e:
            logger.error(
                "autonomous_fix_failed",
                agent=self.agent_name,
                finding_id=finding.id,
                error=str(e),
            )
            raise AgentError(f"Autonomous fix failed: {e}") from e

    def _build_fix_prompt(
        self,
        finding: Finding,
    ) -> str:
        """
        Build prompt for autonomous fixing.

        Args:
            finding: Finding to fix

        Returns:
            Fix prompt
        """
        cwe_info = f" ({finding.cwe.id})" if finding.cwe else ""
        snippet_info = (
            f"\n\nVulnerable code snippet:\n```\n{finding.snippet}\n```"
            if finding.snippet
            else ""
        )

        return f"""Fix this security vulnerability autonomously.

Finding details:
- ID: {finding.id}
- Rule: {finding.rule_id}
- Severity: {finding.severity.value.upper()}{cwe_info}
- Message: {finding.message}
- Location: {finding.file_path}:{finding.start_line}{snippet_info}

Your task:
1. Use Read tool to examine {finding.file_path} around line {finding.start_line}
   (read enough context to understand the vulnerable code)
2. Analyze the vulnerability and plan a secure fix
3. Use Write tool to apply the fix directly to the file
4. Use Read tool again to verify your changes were applied correctly
5. Refine if needed (Write again)
6. When satisfied, call complete_fix with:
   - description: Clear explanation of what you fixed
   - confidence: 0.0-1.0 (be honest about uncertainty)
   - files_modified: List of file paths you changed (e.g., ["path/to/file.ts"])

Important:
- Make minimal changes - only fix the security issue
- Preserve code style, indentation, and formatting
- Maintain existing functionality
- Use language-specific security best practices
- Be conservative - if unsure, call abandon_fix instead

If you cannot create a safe fix:
- Call abandon_fix with a clear explanation why

Remember: You MUST call either complete_fix or abandon_fix when done.
"""
