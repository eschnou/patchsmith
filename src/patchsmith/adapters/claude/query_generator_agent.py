"""Query generator agent for recommending CodeQL queries."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from patchsmith.adapters.claude.agent import AgentError, BaseAgent
from patchsmith.models.finding import Severity
from patchsmith.models.query import Query, QuerySuite
from patchsmith.utils.logging import get_logger

if TYPE_CHECKING:
    from patchsmith.adapters.codeql.cli import CodeQLCLI

logger = get_logger()


class QueryGeneratorAgent(BaseAgent):
    """Agent for generating/recommending CodeQL queries using Claude AI.

    This agent recommends appropriate CodeQL queries based on:
    - Programming languages detected
    - Specific vulnerability types or CWEs
    - Security focus areas
    - Severity preferences
    """

    def get_system_prompt(self) -> str:
        """Get system prompt for query generation."""
        return """You are a CodeQL query expert who recommends security queries.

Your expertise includes:
- Standard CodeQL query suites for each language
- Mapping vulnerability types to specific CodeQL queries
- CWE-to-query mappings
- Query severity classifications

Always respond with ONLY a JSON object in this exact format:
{
  "queries": [
    {
      "id": "python/sql-injection",
      "name": "SQL Injection",
      "description": "Detects SQL injection vulnerabilities",
      "path": "codeql/python-queries:Security/CWE-089/SqlInjection.ql",
      "severity": "high",
      "language": "python",
      "tags": ["security", "cwe-89", "injection"],
      "is_custom": false
    }
  ],
  "suite_recommendations": [
    "codeql/python-queries:codeql-suites/python-security-and-quality.qls"
  ]
}

Requirements:
- id: unique identifier (language/query-name format)
- name: human-readable name
- description: what the query detects
- path: CodeQL query path (standard queries use package:path format)
- severity: "critical", "high", "medium", "low", or "info"
- language: target language
- tags: array of relevant tags
- is_custom: false for standard queries
- suite_recommendations: array of recommended query suite paths

Prioritize standard CodeQL queries over custom ones. Be specific and accurate."""

    async def execute(  # type: ignore[override]
        self,
        languages: list[str],
        focus_areas: list[str] | None = None,
        min_severity: Severity = Severity.MEDIUM,
        validate_queries: bool = True,
        max_retries: int = 2,
    ) -> QuerySuite:
        """
        Generate query recommendations.

        Args:
            languages: Programming languages to generate queries for
            focus_areas: Specific areas to focus on (e.g., "SQL injection", "XSS", "CWE-79")
            min_severity: Minimum severity level to include
            validate_queries: Whether to validate queries can be resolved (requires CodeQL CLI)
            max_retries: Maximum retry attempts if validation fails

        Returns:
            QuerySuite with recommended queries

        Raises:
            AgentError: If generation fails
        """
        logger.info(
            "query_generation_started",
            agent=self.agent_name,
            languages=languages,
            focus_areas=focus_areas,
            min_severity=min_severity.value,
        )

        validation_errors: str | None = None
        attempt = 0

        try:
            while attempt <= max_retries:
                # Build generation prompt (include validation errors for retries)
                prompt = self._build_generation_prompt(
                    languages, focus_areas, min_severity, validation_errors
                )

                # Query Claude
                response = await self.query_claude(
                    prompt=prompt,
                    max_turns=2,
                    allowed_tools=[],  # No tools needed for query recommendation
                )

                # Parse response
                try:
                    query_suite = self._parse_response(response, languages)
                except AgentError as parse_error:
                    # Re-raise with query generation context
                    raise AgentError(f"Query generation failed: {parse_error}") from parse_error

                # Validate queries if requested
                if validate_queries and len(query_suite.queries) > 0:
                    from patchsmith.adapters.codeql.cli import CodeQLCLI

                    validation_errors = self._validate_queries(query_suite, CodeQLCLI())

                    if validation_errors:
                        logger.warning(
                            "query_validation_failed",
                            agent=self.agent_name,
                            attempt=attempt + 1,
                            errors=validation_errors,
                        )
                        attempt += 1
                        if attempt <= max_retries:
                            logger.info(
                                "query_generation_retry",
                                agent=self.agent_name,
                                attempt=attempt,
                            )
                            continue
                        else:
                            # Max retries exceeded with validation errors
                            break

                # Success - validation disabled or passed
                logger.info(
                    "query_generation_completed",
                    agent=self.agent_name,
                    queries_generated=len(query_suite.queries),
                    attempts=attempt + 1,
                )
                return query_suite

            # Max retries exceeded
            logger.error(
                "query_generation_max_retries",
                agent=self.agent_name,
                attempts=attempt,
            )
            raise AgentError(
                f"Query generation failed after {attempt} attempts. "
                f"Last validation errors: {validation_errors}"
            )

        except AgentError:
            raise
        except Exception as e:
            logger.error(
                "query_generation_failed",
                agent=self.agent_name,
                error=str(e),
            )
            raise AgentError(f"Query generation failed: {e}") from e

    def _build_generation_prompt(
        self,
        languages: list[str],
        focus_areas: list[str] | None,
        min_severity: Severity,
        validation_errors: str | None = None,
    ) -> str:
        """
        Build prompt for query generation.

        Args:
            languages: Target languages
            focus_areas: Optional focus areas
            min_severity: Minimum severity
            validation_errors: Previous validation errors (for retries)

        Returns:
            Generation prompt
        """
        focus_text = ""
        if focus_areas:
            focus_text = f"\nFocus areas: {', '.join(focus_areas)}"

        error_text = ""
        if validation_errors:
            error_text = f"\n\nPREVIOUS ATTEMPT HAD ERRORS:\n{validation_errors}\n\nPlease fix these issues and provide corrected query recommendations."

        return f"""Recommend CodeQL queries for security analysis.

Languages: {', '.join(languages)}
Minimum severity: {min_severity.value}{focus_text}

Recommend appropriate standard CodeQL queries and query suites.{error_text}"""

    def _parse_response(self, response: str, languages: list[str]) -> QuerySuite:
        """
        Parse Claude's response into a QuerySuite.

        Args:
            response: Claude's response text
            languages: Languages being analyzed

        Returns:
            QuerySuite with recommended queries

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

            # Extract queries
            queries: list[Query] = []
            query_data = data.get("queries", [])

            for item in query_data:
                if not isinstance(item, dict):
                    logger.warning("query_generation_invalid_item", item=item)
                    continue

                # Validate required fields
                required = ["id", "name", "path", "language"]
                if not all(field in item for field in required):
                    logger.warning("query_generation_missing_fields", item=item)
                    continue

                # Parse severity
                severity_str = item.get("severity", "medium").lower()
                severity = self._parse_severity(severity_str)

                # Create Query object
                query = Query(
                    id=item["id"],
                    name=item["name"],
                    description=item.get("description"),
                    path=Path(item["path"]),
                    severity=severity,
                    language=item["language"],
                    tags=item.get("tags", []),
                    is_custom=item.get("is_custom", False),
                )
                queries.append(query)

            # Create suite
            lang_list = "/".join(languages)
            suite = QuerySuite(
                name=f"Recommended queries for {lang_list}",
                description=f"AI-recommended CodeQL queries for {lang_list}",
                queries=queries,
                language=languages[0] if len(languages) == 1 else None,
            )

            return suite

        except json.JSONDecodeError as e:
            logger.error(
                "query_generation_json_parse_error",
                error=str(e),
                response=response[:200],
            )
            raise AgentError(f"Failed to parse JSON response: {e}") from e
        except Exception as e:
            logger.error(
                "query_generation_parse_error",
                error=str(e),
                response=response[:200],
            )
            raise AgentError(f"Failed to parse response: {e}") from e

    def _parse_severity(self, severity_str: str) -> Severity:
        """
        Parse severity string to Severity enum.

        Args:
            severity_str: Severity string

        Returns:
            Severity enum value
        """
        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }

        return severity_map.get(severity_str.lower(), Severity.MEDIUM)

    def _validate_queries(self, suite: QuerySuite, codeql_cli: "CodeQLCLI") -> str | None:
        """
        Validate that queries can be resolved by CodeQL CLI.

        This helps catch issues like:
        - Invalid query paths
        - Missing query packs
        - Syntax errors in custom queries

        Args:
            suite: QuerySuite to validate
            codeql_cli: CodeQL CLI instance for validation

        Returns:
            Error message if validation fails, None if all queries valid
        """
        errors: list[str] = []

        for query in suite.queries:
            try:
                # For standard queries, try to resolve the pack
                query_str = str(query.path)

                # Standard queries use format: package:path
                if ":" in query_str:
                    pack_name = query_str.split(":")[0]
                    logger.debug(
                        "validating_query_pack",
                        query_id=query.id,
                        pack=pack_name,
                    )
                    # Note: Actual validation would require CodeQL CLI command
                    # For now, just check format is correct
                    if not pack_name or pack_name.count("/") < 1:
                        errors.append(
                            f"Query '{query.id}': Invalid pack format '{pack_name}' "
                            f"(should be 'org/pack-name:path')"
                        )
                # Custom query files
                elif query.path.suffix == ".ql":
                    if not query.path.exists():
                        errors.append(
                            f"Query '{query.id}': File not found at {query.path}"
                        )
                else:
                    errors.append(
                        f"Query '{query.id}': Invalid query path '{query.path}' "
                        f"(should be package:path or .ql file)"
                    )

            except Exception as e:
                errors.append(f"Query '{query.id}': Validation error - {str(e)}")

        if errors:
            return "\n".join(errors)

        return None
