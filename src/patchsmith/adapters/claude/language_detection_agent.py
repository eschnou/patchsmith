"""Language detection agent using Claude AI."""

import json
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server, tool

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.project import LanguageDetection
from patchsmith.utils.logging import get_logger

logger = get_logger()


# Storage for tool results (will be populated by tool calls)
_language_detection_results: list[dict] | None = None


@tool(
    "submit_languages",
    "Submit detected programming languages with confidence scores",
    {
        "languages": list,  # List of {name: str, confidence: float, evidence: list[str]}
    },
)
async def submit_languages_tool(args: dict) -> dict:
    """Tool for submitting language detection results."""
    global _language_detection_results

    languages_data = args.get("languages", [])

    # Handle case where languages might be a JSON string
    if isinstance(languages_data, str):
        try:
            languages_data = json.loads(languages_data)
        except json.JSONDecodeError:
            logger.error("submit_languages_tool_invalid_json", data=languages_data[:200])
            languages_data = []

    _language_detection_results = languages_data

    logger.info(
        "languages_submitted",
        count=len(_language_detection_results),
        languages=[lang.get("name") if isinstance(lang, dict) else str(lang) for lang in _language_detection_results[:5]],
    )

    return {
        "content": [
            {
                "type": "text",
                "text": f"Successfully recorded {len(_language_detection_results)} language(s)",
            }
        ]
    }


class LanguageDetectionAgent(BaseAgent):
    """Agent for detecting programming languages in a codebase using Claude AI.

    This agent analyzes file structures and contents to identify programming
    languages used in a project, providing confidence scores for each detection.
    """

    def get_system_prompt(self) -> str:
        """Get system prompt for language detection."""
        return """You are a programming language detection expert.

When analyzing codebases, examine:
- File extensions (.py, .js, .java, etc.)
- Build/config files (package.json, requirements.txt, pom.xml, go.mod, etc.)
- File structure patterns
- Import/require statements

You have access to these tools:
- Glob: List files matching patterns
- Read: Read file contents
- submit_languages: Submit your findings (YOU MUST call this with your results)

Process:
1. Use Glob to list files and identify extensions
2. Use Read to examine config files if needed
3. Analyze the evidence
4. Call submit_languages tool with your findings

The submit_languages tool expects:
{
  "languages": [
    {"name": "python", "confidence": 0.95, "evidence": ["Found .py files", "requirements.txt present"]},
    {"name": "javascript", "confidence": 0.80, "evidence": ["Found .js files", "package.json present"]}
  ]
}

Requirements:
- name: lowercase language name
- confidence: float 0.0-1.0
- evidence: array of strings explaining detection
- Only include languages with clear evidence

YOU MUST call the submit_languages tool to report your findings."""

    async def execute(  # type: ignore[override]
        self,
        project_path: Path | None = None,
        max_files: int = 100,
    ) -> list[LanguageDetection]:
        """
        Detect programming languages in a project.

        Args:
            project_path: Path to project directory (uses working_dir if None)
            max_files: Maximum number of files to sample for analysis

        Returns:
            List of detected languages with confidence scores

        Raises:
            AgentError: If detection fails
        """
        global _language_detection_results
        _language_detection_results = None  # Reset

        target_path = project_path or self.working_dir

        logger.info(
            "language_detection_started",
            agent=self.agent_name,
            project_path=str(target_path),
        )

        # Validate project path
        if not target_path.exists():
            raise AgentError(f"Project path does not exist: {target_path}")

        if not target_path.is_dir():
            raise AgentError(f"Project path is not a directory: {target_path}")

        try:
            # Create MCP server with custom tool
            server = create_sdk_mcp_server(
                name="language-detection",
                version="1.0.0",
                tools=[submit_languages_tool],
            )

            # Build analysis prompt
            prompt = self._build_analysis_prompt(target_path, max_files)

            # Configure options with custom tool
            options = ClaudeAgentOptions(
                system_prompt=self.get_system_prompt(),
                max_turns=100,  # High limit for complex analysis
                allowed_tools=["Read", "Glob", "mcp__language-detection__submit_languages"],
                mcp_servers={"language-detection": server},
                cwd=str(self.working_dir),
            )

            # Query Claude with custom client
            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                async for message in client.receive_response():
                    message_type = type(message).__name__

                    # Log all message types for debugging
                    logger.debug(
                        "agent_received_message",
                        agent=self.agent_name,
                        message_type=message_type,
                        has_content=hasattr(message, "content"),
                    )

                    # Log full message content for debugging
                    if hasattr(message, "content"):
                        content = message.content
                        if isinstance(content, str):
                            logger.debug(
                                "message_content",
                                agent=self.agent_name,
                                message_type=message_type,
                                content=content[:500],  # Truncate long content
                            )
                        elif isinstance(content, list):
                            for idx, item in enumerate(content):
                                if hasattr(item, "text"):
                                    logger.debug(
                                        "message_content_text",
                                        agent=self.agent_name,
                                        message_type=message_type,
                                        item_index=idx,
                                        text=item.text[:300] if hasattr(item.text, "__len__") else str(item.text)[:300],
                                    )
                                if hasattr(item, "type"):
                                    logger.debug(
                                        "message_content_item",
                                        agent=self.agent_name,
                                        message_type=message_type,
                                        item_index=idx,
                                        item_type=item.type,
                                    )

                    # Check for AssistantMessage with tool use
                    if message_type == "AssistantMessage" and hasattr(message, "content"):
                        for item in message.content if isinstance(message.content, list) else []:
                            if hasattr(item, "type") and item.type == "tool_use":
                                logger.info(
                                    "tool_use_detected",
                                    agent=self.agent_name,
                                    tool_name=getattr(item, "name", "unknown"),
                                    tool_input=getattr(item, "input", {}),
                                )

                    # Log final result
                    if message_type == "ResultMessage":
                        logger.info(
                            "result_message_received",
                            agent=self.agent_name,
                            subtype=getattr(message, "subtype", "unknown"),
                            num_turns=getattr(message, "num_turns", 0),
                            is_error=getattr(message, "is_error", False),
                        )

            # Check if tool was called
            if _language_detection_results is None:
                raise AgentError("Agent did not call submit_languages tool - check max_turns or prompt")

            # Convert to LanguageDetection objects
            languages = self._parse_tool_results(_language_detection_results)

            logger.info(
                "language_detection_completed",
                agent=self.agent_name,
                languages_detected=len(languages),
                languages=[lang.name for lang in languages],
            )

            return languages

        except Exception as e:
            logger.error(
                "language_detection_failed",
                agent=self.agent_name,
                error=str(e),
            )
            raise AgentError(f"Language detection failed: {e}") from e

    def _build_analysis_prompt(self, project_path: Path, max_files: int) -> str:
        """
        Build prompt for language analysis.

        Args:
            project_path: Path to analyze
            max_files: Maximum files to sample

        Returns:
            Analysis prompt
        """
        return f"""Analyze the programming languages in this project:

Path: {project_path}
Max files to sample: {max_files}

Steps:
1. Use Glob tool to list files and identify extensions
2. Use Read tool if needed to examine config files (package.json, requirements.txt, etc.)
3. Analyze the evidence
4. Call the submit_languages tool with your findings

Remember: You MUST use the submit_languages tool to report your results."""

    def _parse_tool_results(self, results: list[dict]) -> list[LanguageDetection]:
        """
        Parse tool results into LanguageDetection objects.

        Args:
            results: List of language dicts from tool

        Returns:
            List of LanguageDetection objects

        Raises:
            AgentError: If parsing fails
        """
        try:
            languages: list[LanguageDetection] = []

            for item in results:
                if not isinstance(item, dict):
                    logger.warning(
                        "language_detection_invalid_item",
                        item=item,
                    )
                    continue

                # Validate required fields
                if "name" not in item or "confidence" not in item:
                    logger.warning(
                        "language_detection_missing_fields",
                        item=item,
                    )
                    continue

                # Handle evidence field
                evidence = item.get("evidence", [])
                if isinstance(evidence, str):
                    evidence = [evidence] if evidence else []
                elif not isinstance(evidence, list):
                    evidence = []

                # Create LanguageDetection object
                lang = LanguageDetection(
                    name=item["name"],
                    confidence=float(item["confidence"]),
                    evidence=evidence,
                )
                languages.append(lang)

            return languages

        except Exception as e:
            logger.error(
                "language_detection_parse_tool_error",
                error=str(e),
            )
            raise AgentError(f"Failed to parse tool results: {e}") from e

    def _parse_response(self, response: str) -> list[LanguageDetection]:
        """
        Parse Claude's response into LanguageDetection objects.

        Args:
            response: Claude's response text

        Returns:
            List of LanguageDetection objects

        Raises:
            AgentError: If parsing fails
        """
        try:
            # Try to find JSON in the response
            json_start = response.find("[")
            json_end = response.rfind("]") + 1

            if json_start == -1 or json_end == 0:
                raise AgentError("No JSON array found in response")

            json_str = response[json_start:json_end]
            data = json.loads(json_str)

            if not isinstance(data, list):
                raise AgentError("Response is not a JSON array")

            # Convert to LanguageDetection objects
            languages: list[LanguageDetection] = []
            for item in data:
                if not isinstance(item, dict):
                    logger.warning(
                        "language_detection_invalid_item",
                        item=item,
                    )
                    continue

                # Validate required fields
                if "name" not in item or "confidence" not in item:
                    logger.warning(
                        "language_detection_missing_fields",
                        item=item,
                    )
                    continue

                # Handle evidence field - convert string to list if needed
                evidence = item.get("evidence", [])
                if isinstance(evidence, str):
                    evidence = [evidence] if evidence else []
                elif not isinstance(evidence, list):
                    evidence = []

                # Create LanguageDetection object
                lang = LanguageDetection(
                    name=item["name"],
                    confidence=float(item["confidence"]),
                    evidence=evidence,
                )
                languages.append(lang)

            if not languages:
                logger.warning(
                    "language_detection_no_languages",
                    response=response,
                )

            return languages

        except json.JSONDecodeError as e:
            logger.error(
                "language_detection_json_parse_error",
                error=str(e),
                response=response[:200],
            )
            raise AgentError(f"Failed to parse JSON response: {e}") from e
        except Exception as e:
            logger.error(
                "language_detection_parse_error",
                error=str(e),
                response=response[:200],
            )
            raise AgentError(f"Failed to parse response: {e}") from e
