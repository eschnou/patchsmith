"""Query finetuning service for generating custom CodeQL queries."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from patchsmith.adapters.claude.custom_query_generator_agent import (
    CustomQueryGeneratorAgent,
)
from patchsmith.adapters.claude.language_detection_agent import LanguageDetectionAgent
from patchsmith.adapters.claude.vulnerability_brainstorm_agent import (
    VulnerabilityBrainstormAgent,
)
from patchsmith.adapters.codeql.cli import CodeQLCLI
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import Severity
from patchsmith.models.project import ProjectInfo
from patchsmith.models.query import Query, QuerySuite
from patchsmith.repositories.project_repository import ProjectRepository
from patchsmith.services.base_service import BaseService
from patchsmith.utils.logging import get_logger

logger = get_logger()


class QueryFinetuneService(BaseService):
    """Service for generating and validating custom CodeQL queries.

    This service coordinates:
    1. Project context analysis
    2. Custom query generation via CustomQueryGeneratorAgent
    3. Query compilation and validation
    4. Query persistence to .patchsmith/queries/
    5. Metadata management

    The service is presentation-agnostic and emits progress via callbacks.
    """

    def __init__(
        self,
        config: PatchsmithConfig,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
        thinking_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Initialize query finetune service.

        Args:
            config: Patchsmith configuration
            progress_callback: Optional progress callback
            thinking_callback: Optional callback for agent thinking updates
        """
        super().__init__(config, progress_callback)
        self.thinking_callback = thinking_callback

        # Initialize adapters
        self.codeql = CodeQLCLI()

    async def finetune_queries(
        self,
        project_path: Path,
        focus_areas: list[str] | None = None,
        max_queries: int = 5,
        languages: list[str] | None = None,
    ) -> QuerySuite:
        """
        Generate custom CodeQL queries for a project.

        Args:
            project_path: Path to project
            focus_areas: Specific security areas to focus on (e.g., ["authentication", "SQL injection"])
            max_queries: Maximum number of queries to generate
            languages: Target languages (auto-detect if None)

        Returns:
            QuerySuite with generated and validated queries

        Raises:
            Exception: If query generation fails
        """
        self._emit_progress("finetune_started", project_path=str(project_path))

        try:
            # Step 1: Detect languages if not provided (or load from cache)
            if not languages:
                # Try to load from cache first
                project_info = ProjectRepository.load(project_path)

                if project_info and project_info.languages:
                    # Use cached language detection
                    languages = project_info.get_language_names()
                    logger.info(
                        "language_detection_cached",
                        languages=languages,
                        count=len(languages),
                    )
                    self._emit_progress(
                        "language_detection_completed",
                        languages=languages,
                        count=len(languages),
                        cached=True,
                    )
                else:
                    # Perform language detection
                    self._emit_progress("language_detection_started")

                    def agent_progress_callback(current_turn: int, max_turns: int):
                        self._emit_progress(
                            "agent_turn_progress",
                            current_turn=current_turn,
                            max_turns=max_turns,
                        )

                    language_agent = LanguageDetectionAgent(
                        working_dir=project_path,
                        thinking_callback=self.thinking_callback,
                        progress_callback=agent_progress_callback,
                    )
                    detected_languages = await language_agent.execute(
                        project_path=project_path
                    )

                    if self.thinking_callback:
                        self.thinking_callback("")

                    languages = [lang.name for lang in detected_languages]
                    self._emit_progress(
                        "language_detection_completed",
                        languages=languages,
                        count=len(languages),
                    )

                    # Save project info for future use
                    project_info = ProjectInfo(
                        name=project_path.name,
                        root=project_path,
                        languages=detected_languages,
                    )
                    ProjectRepository.save(project_info)

            if not languages:
                raise ValueError("No languages detected or provided")

            # Step 2: Analyze project context
            self._emit_progress("project_analysis_started")
            project_context = await self._analyze_project_context(
                project_path, languages
            )
            self._emit_progress("project_analysis_completed")

            # Step 3: Determine vulnerabilities to target
            if focus_areas:
                # User-specified focus areas (manual override)
                self._emit_progress("vulnerability_targeting_started")
                vulnerability_targets = self._build_targets_from_focus_areas(
                    languages, focus_areas, max_queries
                )
                self._emit_progress(
                    "vulnerability_targeting_completed",
                    target_count=len(vulnerability_targets),
                )
            else:
                # AI-powered vulnerability brainstorming
                self._emit_progress("vulnerability_brainstorming_started")

                def brainstorm_agent_progress(current_turn: int, max_turns: int):
                    self._emit_progress(
                        "agent_turn_progress",
                        current_turn=current_turn,
                        max_turns=max_turns,
                    )

                brainstorm_agent = VulnerabilityBrainstormAgent(
                    working_dir=project_path,
                    thinking_callback=self.thinking_callback,
                    progress_callback=brainstorm_agent_progress,
                )
                suggestions = await brainstorm_agent.execute(
                    project_path=project_path,
                    languages=languages,
                    project_context=project_context,
                    max_suggestions=max_queries,
                )

                if self.thinking_callback:
                    self.thinking_callback("")

                # Convert suggestions to vulnerability targets
                vulnerability_targets = [
                    (s.language, s.vulnerability_type, s.severity) for s in suggestions
                ]

                logger.info(
                    "vulnerability_suggestions_generated",
                    count=len(suggestions),
                    top_suggestions=[s.vulnerability_type for s in suggestions[:3]],
                )

                self._emit_progress(
                    "vulnerability_brainstorming_completed",
                    target_count=len(vulnerability_targets),
                )

            # Step 3.5: Setup QL pack structure for each language
            self._emit_progress("ql_pack_setup_started")
            language_packs: dict[str, Path] = {}
            total_languages = len(languages)

            for index, lang in enumerate(languages, start=1):
                pack_dir = project_path / ".patchsmith" / "queries" / lang

                # Emit progress for this pack
                self._emit_progress(
                    "ql_pack_setup_progress",
                    current=index,
                    total=total_languages,
                    language=lang,
                )

                try:
                    # Create QL pack structure
                    self.codeql.create_ql_pack(pack_dir, lang)

                    # Install dependencies (downloads standard libraries)
                    self.codeql.install_pack_dependencies(pack_dir)

                    language_packs[lang] = pack_dir

                    logger.info(
                        "ql_pack_initialized",
                        language=lang,
                        pack_dir=str(pack_dir),
                    )
                except Exception as e:
                    logger.warning(
                        "ql_pack_setup_failed",
                        language=lang,
                        error=str(e),
                    )
                    # Continue even if pack setup fails for one language

            self._emit_progress(
                "ql_pack_setup_completed",
                languages_setup=list(language_packs.keys()),
            )

            # Step 4: Generate queries
            queries: list[Query] = []
            total = len(vulnerability_targets)

            for index, (lang, vuln_type, severity) in enumerate(
                vulnerability_targets, start=1
            ):
                self._emit_progress(
                    "query_generation_progress",
                    current=index,
                    total=total,
                    language=lang,
                    vulnerability=vuln_type,
                )

                # Create agent for this query
                def query_agent_progress(current_turn: int, max_turns: int):
                    self._emit_progress(
                        "agent_turn_progress",
                        current_turn=current_turn,
                        max_turns=max_turns,
                    )

                agent = CustomQueryGeneratorAgent(
                    working_dir=project_path,
                    thinking_callback=self.thinking_callback,
                    progress_callback=query_agent_progress,
                )

                try:
                    # Get pack directory for this language
                    pack_dir = language_packs.get(lang)
                    if not pack_dir:
                        # Skip if pack setup failed for this language
                        logger.warning(
                            "skipping_query_no_pack",
                            language=lang,
                            vulnerability=vuln_type,
                        )
                        continue

                    # Generate and validate query (agent handles iteration autonomously)
                    query_id, query_content = await agent.execute(
                        language=lang,
                        project_context=project_context,
                        vulnerability_type=vuln_type,
                        severity=severity,
                        codeql_cli=self.codeql,
                        pack_dir=pack_dir,
                    )

                    if self.thinking_callback:
                        self.thinking_callback("")

                    # Save query to filesystem
                    query_path = self._save_query(
                        project_path, lang, query_id, query_content
                    )

                    # Create Query model
                    query = Query(
                        id=query_id,
                        name=vuln_type,
                        description=f"Custom query for {vuln_type} in {lang}",
                        path=query_path,
                        severity=severity,
                        language=lang,
                        tags=["security", "custom", f"language:{lang}"],
                        is_custom=True,
                    )
                    queries.append(query)

                    logger.info(
                        "custom_query_generated",
                        query_id=query_id,
                        language=lang,
                        vulnerability=vuln_type,
                    )

                except Exception as e:
                    logger.warning(
                        "custom_query_generation_failed",
                        language=lang,
                        vulnerability=vuln_type,
                        error=str(e),
                    )
                    # Continue with other queries even if one fails
                    self._emit_progress(
                        "query_generation_failed",
                        language=lang,
                        vulnerability=vuln_type,
                        error=str(e),
                    )

            # Step 5: Save metadata
            self._emit_progress("metadata_save_started")
            query_suite = QuerySuite(
                name=f"Custom queries for {project_path.name}",
                description=f"AI-generated custom CodeQL queries for {', '.join(languages)}",
                queries=queries,
                language=languages[0] if len(languages) == 1 else None,
            )
            self._save_metadata(project_path, query_suite)
            self._emit_progress("metadata_save_completed")

            self._emit_progress(
                "finetune_completed",
                queries_generated=len(queries),
                languages=languages,
            )

            return query_suite

        except Exception as e:
            self._emit_progress("finetune_failed", error=str(e))
            logger.error(
                "finetune_service_error",
                project_path=str(project_path),
                error=str(e),
            )
            raise

    async def _analyze_project_context(
        self, project_path: Path, languages: list[str]
    ) -> str:
        """
        Analyze project to understand architecture and patterns.

        Args:
            project_path: Path to project
            languages: Detected languages

        Returns:
            Project context description
        """
        # For now, create a simple context from filesystem analysis
        # Future: Could use an agent to analyze the codebase
        context_parts = [f"Languages: {', '.join(languages)}"]

        # Detect frameworks by looking for common files
        frameworks = []
        if (project_path / "package.json").exists():
            frameworks.append("Node.js/npm")
        if (project_path / "requirements.txt").exists() or (
            project_path / "pyproject.toml"
        ).exists():
            frameworks.append("Python")
        if (project_path / "pom.xml").exists():
            frameworks.append("Maven/Java")
        if (project_path / "go.mod").exists():
            frameworks.append("Go modules")

        if frameworks:
            context_parts.append(f"Frameworks: {', '.join(frameworks)}")

        # Check for common patterns
        if (project_path / "src").exists():
            context_parts.append("Source code in src/ directory")
        if (project_path / "tests").exists() or (project_path / "test").exists():
            context_parts.append("Contains test suite")

        return "\n".join(context_parts)

    def _build_targets_from_focus_areas(
        self,
        languages: list[str],
        focus_areas: list[str],
        max_queries: int,
    ) -> list[tuple[str, str, Severity]]:
        """
        Build vulnerability targets from user-specified focus areas.

        Args:
            languages: Project languages
            focus_areas: User-specified focus areas
            max_queries: Maximum queries to generate

        Returns:
            List of (language, vulnerability_type, severity) tuples
        """
        targets: list[tuple[str, str, Severity]] = []

        for lang in languages:
            for area in focus_areas[:max_queries]:
                targets.append((lang, area, Severity.HIGH))

        return targets[:max_queries]

    def _determine_vulnerability_targets(
        self,
        languages: list[str],
        focus_areas: list[str] | None,
        max_queries: int,
    ) -> list[tuple[str, str, Severity]]:
        """
        Determine which vulnerabilities to target with custom queries (LEGACY/FALLBACK).

        NOTE: This is now a fallback method. The main workflow uses
        VulnerabilityBrainstormAgent for AI-powered suggestions.

        Args:
            languages: Project languages
            focus_areas: User-specified focus areas
            max_queries: Maximum queries to generate

        Returns:
            List of (language, vulnerability_type, severity) tuples
        """
        targets: list[tuple[str, str, Severity]] = []

        # If focus areas provided, use those
        if focus_areas:
            return self._build_targets_from_focus_areas(
                languages, focus_areas, max_queries
            )

        # Default vulnerability types by language
        default_vulns = {
            "python": [
                ("SQL injection in ORM queries", Severity.HIGH),
                ("Command injection in subprocess", Severity.CRITICAL),
                ("Path traversal in file operations", Severity.HIGH),
                ("Unsafe deserialization (pickle)", Severity.CRITICAL),
                ("Hardcoded secrets", Severity.HIGH),
            ],
            "javascript": [
                ("SQL injection in database queries", Severity.HIGH),
                ("XSS via DOM manipulation", Severity.HIGH),
                ("Prototype pollution", Severity.HIGH),
                ("Command injection in child_process", Severity.CRITICAL),
                ("Insecure random number generation", Severity.MEDIUM),
            ],
            "typescript": [
                ("SQL injection in database queries", Severity.HIGH),
                ("XSS via DOM manipulation", Severity.HIGH),
                ("Prototype pollution", Severity.HIGH),
                ("Type assertion bypasses", Severity.MEDIUM),
            ],
            "java": [
                ("SQL injection in JDBC", Severity.HIGH),
                ("XXE in XML parsing", Severity.HIGH),
                ("Path traversal in file operations", Severity.HIGH),
                ("Unsafe deserialization", Severity.CRITICAL),
            ],
            "go": [
                ("SQL injection in database/sql", Severity.HIGH),
                ("Command injection in exec", Severity.CRITICAL),
                ("Path traversal", Severity.HIGH),
            ],
        }

        # Select vulnerabilities for each language
        for lang in languages:
            lang_lower = lang.lower()
            vulns = default_vulns.get(lang_lower, [])

            for vuln_type, severity in vulns:
                if len(targets) >= max_queries:
                    break
                targets.append((lang, vuln_type, severity))

            if len(targets) >= max_queries:
                break

        return targets[:max_queries]

    def _save_query(
        self, project_path: Path, language: str, query_id: str, query_content: str
    ) -> Path:
        """
        Save query to filesystem (or return path if already saved).

        Args:
            project_path: Project root path
            language: Query language
            query_id: Query identifier
            query_content: Query .ql content

        Returns:
            Path to saved query file
        """
        # Create queries directory structure
        queries_dir = project_path / ".patchsmith" / "queries" / language
        queries_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from query_id
        # Remove "custom/" prefix and language prefix if present
        filename = query_id.replace("custom/", "").replace(f"{language}/", "")
        filename = filename.replace("/", "_") + ".ql"

        query_path = queries_dir / filename

        # Check if already saved (by agent during compilation)
        if not query_path.exists():
            # Save query content
            query_path.write_text(query_content)

            logger.info(
                "custom_query_saved",
                query_id=query_id,
                path=str(query_path),
            )
        else:
            logger.debug(
                "custom_query_already_saved",
                query_id=query_id,
                path=str(query_path),
            )

        return query_path

    def _save_metadata(self, project_path: Path, query_suite: QuerySuite) -> None:
        """
        Save query suite metadata.

        Args:
            project_path: Project root path
            query_suite: Query suite with generated queries
        """
        queries_dir = project_path / ".patchsmith" / "queries"
        metadata_path = queries_dir / "metadata.json"

        # Convert to JSON-serializable format
        metadata = {
            "name": query_suite.name,
            "description": query_suite.description,
            "generated_at": datetime.now().isoformat(),
            "queries": [
                {
                    "id": q.id,
                    "name": q.name,
                    "description": q.description,
                    "path": str(q.path.relative_to(project_path)),
                    "severity": q.severity.value,
                    "language": q.language,
                    "tags": q.tags,
                    "is_custom": q.is_custom,
                }
                for q in query_suite.queries
            ],
        }

        metadata_path.write_text(json.dumps(metadata, indent=2))

        logger.info(
            "query_metadata_saved",
            path=str(metadata_path),
            query_count=len(query_suite.queries),
        )
