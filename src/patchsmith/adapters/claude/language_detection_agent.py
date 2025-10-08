"""Language detection agent using Claude AI."""

import json
from pathlib import Path

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.project import LanguageDetection
from patchsmith.utils.logging import get_logger

logger = get_logger()


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

Always respond with ONLY a JSON array in this exact format:
[
  {"name": "python", "confidence": 0.95, "evidence": ["Found .py files", "requirements.txt present"]},
  {"name": "javascript", "confidence": 0.80, "evidence": ["Found .js files", "package.json present"]}
]

Requirements:
- name: lowercase language name
- confidence: float 0.0-1.0
- evidence: array of strings explaining detection
- Only include languages with clear evidence
- Be accurate and concise"""

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
            # Build analysis prompt
            prompt = self._build_analysis_prompt(target_path, max_files)

            # Query Claude
            response = await self.query_claude(
                prompt=prompt,
                max_turns=2,  # Language detection is straightforward
                allowed_tools=["Read", "Glob"],  # Allow file reading
            )

            # Parse response
            languages = self._parse_response(response)

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

Use the Glob and Read tools to examine the codebase."""

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
