"""Analysis service for orchestrating the complete security analysis workflow."""

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from patchsmith.adapters.claude.detailed_security_analysis_agent import (
    DetailedSecurityAnalysisAgent,
)
from patchsmith.adapters.claude.language_detection_agent import LanguageDetectionAgent
from patchsmith.adapters.claude.triage_agent import TriageAgent
from patchsmith.adapters.codeql.cli import CodeQLCLI
from patchsmith.adapters.codeql.parsers import SARIFParser
from patchsmith.models.analysis import AnalysisResult, AnalysisStatistics, TriageResult
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import DetailedSecurityAssessment, Finding, Severity
from patchsmith.models.project import LanguageDetection, ProjectInfo
from patchsmith.repositories.project_repository import ProjectRepository
from patchsmith.services.base_service import BaseService
from patchsmith.utils.logging import get_logger

logger = get_logger()


class AnalysisService(BaseService):
    """Service for orchestrating complete security analysis workflow.

    This service coordinates:
    1. Language detection
    2. CodeQL database creation and query execution
    3. Finding parsing
    4. Triage (high-level review)
    5. Detailed security analysis (comprehensive assessment)
    6. Statistics computation

    The service is presentation-agnostic and emits progress via callbacks.
    """

    def __init__(
        self,
        config: PatchsmithConfig,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
        thinking_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Initialize analysis service.

        Args:
            config: Patchsmith configuration
            progress_callback: Optional progress callback
            thinking_callback: Optional callback for agent thinking updates
        """
        super().__init__(config, progress_callback)
        self.thinking_callback = thinking_callback

        # Initialize adapters
        # CodeQL CLI path defaults to "codeql" (assumes it's in PATH)
        self.codeql = CodeQLCLI()
        self.sarif_parser = SARIFParser()

    async def analyze_project(
        self,
        project_path: Path,
        perform_triage: bool = True,
        perform_detailed_analysis: bool = True,
        investigate_all_groups: bool = False,
        detailed_analysis_limit: int | None = None,
        custom_only: bool = False,
    ) -> tuple[AnalysisResult, list[TriageResult] | None, dict[str, DetailedSecurityAssessment] | None]:
        """
        Perform complete security analysis on a project.

        Args:
            project_path: Path to project to analyze
            perform_triage: Whether to perform triage (grouping and prioritization)
            perform_detailed_analysis: Whether to perform detailed analysis on findings
            investigate_all_groups: If True, investigate all groups; if False, only recommended
            detailed_analysis_limit: Max findings to analyze in detail (None = all that match criteria)
            custom_only: Whether to run only custom queries (skip standard queries)

        Returns:
            Tuple of (AnalysisResult, triage_results, detailed_assessments)

        Raises:
            Exception: If analysis fails at any stage
        """
        self._emit_progress("analysis_started", project_path=str(project_path))

        try:
            # Step 1: Detect languages (or load from cache)
            project_info = ProjectRepository.load(project_path)

            if project_info and project_info.languages:
                # Use cached language detection
                languages = project_info.languages
                language_names = project_info.get_language_names()
                logger.info(
                    "language_detection_cached",
                    languages=language_names,
                    count=len(language_names),
                )
                self._emit_progress(
                    "language_detection_completed",
                    languages=language_names,
                    count=len(language_names),
                    cached=True,
                )
            else:
                # Perform language detection
                self._emit_progress("language_detection_started")

                # Create agent progress callback that updates the language_detection task
                def agent_progress_callback(current_turn: int, max_turns: int):
                    # Emit progress based on agent turns
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
                languages = await language_agent.execute(project_path=project_path)

                # Clear thinking display when agent completes
                if self.thinking_callback:
                    self.thinking_callback("")

                language_names = [lang.name for lang in languages]
                self._emit_progress(
                    "language_detection_completed",
                    languages=language_names,
                    count=len(languages),
                )

                # Save project info for future use
                project_info = ProjectInfo(
                    name=project_path.name,
                    root=project_path,
                    languages=languages,
                )
                ProjectRepository.save(project_info)

            if not languages:
                raise ValueError("No languages detected in project")

            # Step 2: Create CodeQL database for primary language
            primary_language = languages[0]
            self._emit_progress(
                "codeql_database_creation_started",
                language=primary_language.name,
            )

            # Map language to CodeQL language
            codeql_language = self._map_language_to_codeql(primary_language.name)

            # Create .patchsmith directory for all artifacts
            patchsmith_dir = project_path / ".patchsmith"
            patchsmith_dir.mkdir(exist_ok=True)

            # Ensure .gitignore exists to prevent committing temporary files
            gitignore_path = patchsmith_dir / ".gitignore"
            if not gitignore_path.exists():
                gitignore_content = """# Patchsmith temporary files - do not commit
# Only config.json should be committed

# CodeQL databases
db_*/

# SARIF results
*.sarif
results_*.sarif

# Temporary directories
results/
cache/

# Reports are generated, not source files
reports/
"""
                gitignore_path.write_text(gitignore_content)

            db_path = patchsmith_dir / f"db_{codeql_language}"

            self.codeql.create_database(
                source_root=project_path,
                db_path=db_path,
                language=codeql_language,
                threads=self.config.codeql.threads,
                overwrite=False,
            )
            self._emit_progress(
                "codeql_database_created",
                database_path=str(db_path),
            )

            # Step 3: Run CodeQL queries (standard or skip if custom-only)
            if not custom_only:
                self._emit_progress("codeql_queries_started")
                query_suite = self._get_query_suite(codeql_language)
                results_path = patchsmith_dir / f"results_{codeql_language}.sarif"

                self.codeql.run_queries(
                    db_path=db_path,
                    query_path=query_suite,
                    output_format="sarif-latest",
                    output_path=results_path,
                    threads=self.config.codeql.threads,
                    download=True,
                )
                self._emit_progress(
                    "codeql_queries_completed",
                    results_path=str(results_path),
                )
            else:
                # Custom-only mode: create empty results file
                results_path = patchsmith_dir / f"results_{codeql_language}.sarif"
                logger.info("custom_only_mode", message="Skipping standard queries")

            # Step 3.5: Run custom queries if they exist
            # Use detected language name (not CodeQL mapped name) to find custom queries
            # e.g., look in .patchsmith/queries/typescript/ not /javascript/
            custom_queries_dir = self._get_custom_queries_dir(
                project_path, primary_language.name
            )
            if custom_queries_dir and custom_queries_dir.exists():
                self._emit_progress("custom_queries_started")
                custom_results_path = (
                    patchsmith_dir / f"results_custom_{codeql_language}.sarif"
                )

                try:
                    self.codeql.run_queries(
                        db_path=db_path,
                        query_path=custom_queries_dir,
                        output_format="sarif-latest",
                        output_path=custom_results_path,
                        threads=self.config.codeql.threads,
                        download=False,  # Custom queries are local
                    )
                    self._emit_progress(
                        "custom_queries_completed",
                        results_path=str(custom_results_path),
                    )
                except Exception as e:
                    logger.warning(
                        "custom_queries_failed",
                        error=str(e),
                        custom_queries_dir=str(custom_queries_dir),
                    )
                    self._emit_progress(
                        "custom_queries_failed",
                        error=str(e),
                    )
                    # Continue with standard results even if custom queries fail
                    custom_results_path = None
            else:
                custom_results_path = None

            # Step 4: Parse SARIF results (standard + custom)
            self._emit_progress("sarif_parsing_started")

            # Parse standard results (if not custom-only)
            if not custom_only and results_path.exists():
                findings = self.sarif_parser.parse_file(results_path)
            else:
                findings = []

            # Add findings from custom queries if available
            if custom_results_path and custom_results_path.exists():
                try:
                    custom_findings = self.sarif_parser.parse_file(custom_results_path)
                    findings.extend(custom_findings)
                    logger.info(
                        "custom_findings_added",
                        count=len(custom_findings),
                    )
                except Exception as e:
                    logger.warning(
                        "custom_findings_parse_failed",
                        error=str(e),
                    )

            # Assign short, user-friendly IDs (F-1, F-2, etc.)
            findings = self._assign_short_ids(findings)

            self._emit_progress(
                "sarif_parsing_completed",
                finding_count=len(findings),
            )

            # Step 5: Triage (optional)
            triage_results = None
            if perform_triage and len(findings) > 0:
                self._emit_progress("triage_started", finding_count=len(findings))

                # Create agent progress callback for triage
                def triage_progress_callback(current_turn: int, max_turns: int):
                    self._emit_progress(
                        "agent_turn_progress",
                        current_turn=current_turn,
                        max_turns=max_turns,
                    )

                triage_agent = TriageAgent(
                    working_dir=project_path,
                    thinking_callback=self.thinking_callback,
                    progress_callback=triage_progress_callback,
                )
                # Top N findings/groups to mark for detailed AI investigation
                # Note: max_results is for loading findings from CodeQL (1000+)
                # This top_n is for deep investigation - keep it reasonable (10-15)
                top_n_investigate = 10
                triage_results = await triage_agent.execute(
                    findings=findings,
                    top_n=top_n_investigate,
                )

                # Clear thinking display when agent completes
                if self.thinking_callback:
                    self.thinking_callback("")

                recommended_count = sum(1 for t in triage_results if t.recommended_for_analysis)
                self._emit_progress(
                    "triage_completed",
                    prioritized_count=len(triage_results),
                    recommended_count=recommended_count,
                )

            # Step 6: Detailed security analysis (optional)
            detailed_assessments = None
            if perform_detailed_analysis and findings:
                # Determine which findings to analyze
                findings_to_analyze = []

                if triage_results:
                    # Triage was performed - work with grouped findings
                    if investigate_all_groups:
                        # --investigate-all: analyze ALL groups (not just recommended)
                        triage_to_process = triage_results
                    else:
                        # --investigate: analyze only recommended groups
                        triage_to_process = [t for t in triage_results if t.recommended_for_analysis]

                    # Apply limit if specified
                    if detailed_analysis_limit is not None:
                        triage_to_process = triage_to_process[:detailed_analysis_limit]

                    # Convert triage results to findings
                    for triage in triage_to_process:
                        finding = next((f for f in findings if f.id == triage.finding_id), None)
                        if finding:
                            findings_to_analyze.append(finding)
                else:
                    # Fallback: No triage performed (shouldn't happen with always-triage)
                    # Analyze all findings directly
                    findings_to_analyze = (
                        findings[:detailed_analysis_limit]
                        if detailed_analysis_limit is not None
                        else findings
                    )

                if findings_to_analyze:
                    self._emit_progress(
                        "detailed_analysis_started",
                        finding_count=len(findings_to_analyze),
                    )

                    # Create agent progress callback for detailed analysis
                    def detailed_progress_callback(current_turn: int, max_turns: int):
                        self._emit_progress(
                            "agent_turn_progress",
                            current_turn=current_turn,
                            max_turns=max_turns,
                        )

                    # Create analysis agent with callbacks
                    analysis_agent = DetailedSecurityAnalysisAgent(
                        working_dir=project_path,
                        thinking_callback=self.thinking_callback,
                        progress_callback=detailed_progress_callback,
                    )

                    # Perform analysis with per-finding progress (with grouping info)
                    detailed_assessments = await self._analyze_findings_with_progress(
                        analysis_agent,
                        findings_to_analyze,
                        triage_results=triage_results,
                    )

                    # Clear thinking display when agent completes
                    if self.thinking_callback:
                        self.thinking_callback("")

                    self._emit_progress(
                        "detailed_analysis_completed",
                        analyzed_count=len(detailed_assessments),
                        false_positives=sum(
                            1 for a in detailed_assessments.values() if a.is_false_positive
                        ),
                    )

            # Step 7: Compute statistics
            self._emit_progress("statistics_computation_started")
            statistics = self._compute_statistics(findings)
            self._emit_progress("statistics_computation_completed")

            # Step 8: Create analysis result
            analysis_result = AnalysisResult(
                project_name=project_path.name,
                project_path=project_path,
                findings=findings,
                statistics=statistics,
                timestamp=datetime.now(),
                languages_analyzed=[lang.name for lang in languages],
            )

            self._emit_progress(
                "analysis_completed",
                total_findings=len(findings),
                critical_count=statistics.get_critical_count(),
                high_count=statistics.get_high_count(),
            )

            return analysis_result, triage_results, detailed_assessments

        except Exception as e:
            self._emit_progress("analysis_failed", error=str(e))
            logger.error(
                "analysis_service_error",
                project_path=str(project_path),
                error=str(e),
            )
            raise

    async def _analyze_findings_with_progress(
        self,
        analysis_agent: DetailedSecurityAnalysisAgent,
        findings: list[Finding],
        triage_results: list[TriageResult] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze findings one by one with progress updates.

        Args:
            analysis_agent: The detailed analysis agent
            findings: List of findings to analyze
            triage_results: Optional triage results containing grouping information

        Returns:
            Dictionary of finding_id to DetailedSecurityAssessment
        """
        from patchsmith.adapters.claude.detailed_security_analysis_agent import (
            DetailedSecurityAssessment,
        )

        # Build finding groups dict from triage results
        finding_groups: dict[str, list[str]] = {}
        if triage_results:
            for triage in triage_results:
                if triage.related_finding_ids:
                    finding_groups[triage.finding_id] = triage.related_finding_ids

        assessments: dict[str, DetailedSecurityAssessment] = {}
        total = len(findings)

        for index, finding in enumerate(findings, start=1):
            # Check if this is a grouped finding
            related_ids = finding_groups.get(finding.id, [])
            is_group = len(related_ids) > 0
            total_instances = 1 + len(related_ids) if is_group else 1

            # Emit progress for this specific finding
            self._emit_progress(
                "detailed_analysis_finding_progress",
                current=index,
                total=total,
                finding_id=finding.id,
                severity=finding.severity.value if finding.severity else "unknown",
                is_group=is_group,
                total_instances=total_instances,
            )

            # Analyze single finding with group context
            result = await analysis_agent.execute([finding], finding_groups=finding_groups)
            if result:
                assessments.update(result)

        return assessments

    def _assign_short_ids(self, findings: list[Finding]) -> list[Finding]:
        """
        Assign short, user-friendly IDs to findings.

        Original IDs from CodeQL are very long (e.g., js/property-access-on-non-object_index-C_YCkAbh.js_1).
        This replaces them with short sequential IDs like F-1, F-2, F-3, etc.

        The original rule_id is preserved in the rule_id field for reference.

        Args:
            findings: List of findings with long IDs

        Returns:
            List of findings with short IDs assigned
        """
        for index, finding in enumerate(findings, start=1):
            # Store original ID in a way that's still accessible if needed
            # but assign a short, memorable ID
            finding.id = f"F-{index}"

        logger.info(
            "assigned_short_ids",
            count=len(findings),
            id_range=f"F-1 to F-{len(findings)}" if findings else "none",
        )

        return findings

    def _map_language_to_codeql(self, language: str) -> str:
        """
        Map detected language to CodeQL language name.

        Args:
            language: Detected language name

        Returns:
            CodeQL language name
        """
        language_mapping = {
            "javascript": "javascript",
            "typescript": "javascript",
            "python": "python",
            "java": "java",
            "go": "go",
            "cpp": "cpp",
            "c": "cpp",
            "csharp": "csharp",
            "ruby": "ruby",
        }
        return language_mapping.get(language.lower(), language.lower())

    def _get_query_suite(self, language: str) -> str:
        """
        Get CodeQL query suite for a language.

        Args:
            language: CodeQL language name

        Returns:
            Query suite path
        """
        query_suites = {
            "python": "codeql/python-queries:codeql-suites/python-security-and-quality.qls",
            "javascript": "codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls",
            "java": "codeql/java-queries:codeql-suites/java-security-and-quality.qls",
            "go": "codeql/go-queries:codeql-suites/go-security-and-quality.qls",
            "cpp": "codeql/cpp-queries:codeql-suites/cpp-security-and-quality.qls",
            "csharp": "codeql/csharp-queries:codeql-suites/csharp-security-and-quality.qls",
            "ruby": "codeql/ruby-queries:codeql-suites/ruby-security-and-quality.qls",
        }
        return query_suites.get(language, f"codeql/{language}-queries")

    def _get_custom_queries_dir(
        self, project_path: Path, language: str
    ) -> Path | None:
        """
        Get custom queries directory for a language.

        Args:
            project_path: Project root path
            language: CodeQL language name

        Returns:
            Path to custom queries directory, or None if not found
        """
        custom_dir = project_path / ".patchsmith" / "queries" / language

        # Check if directory exists and contains .ql files
        if custom_dir.exists() and custom_dir.is_dir():
            ql_files = list(custom_dir.glob("*.ql"))
            if ql_files:
                logger.info(
                    "custom_queries_found",
                    language=language,
                    count=len(ql_files),
                    directory=str(custom_dir),
                )
                return custom_dir

        return None

    def _compute_statistics(self, findings: list[Finding]) -> AnalysisStatistics:
        """
        Compute statistics for findings.

        Args:
            findings: List of findings

        Returns:
            AnalysisStatistics object
        """
        by_severity: dict[Severity, int] = {}
        by_language: dict[str, int] = {}
        by_cwe: dict[str, int] = {}
        false_positives = 0

        for finding in findings:
            # Count by severity
            by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

            # Count by CWE
            if finding.cwe:
                by_cwe[finding.cwe.id] = by_cwe.get(finding.cwe.id, 0) + 1

            # Count false positives
            if finding.false_positive_score and finding.false_positive_score.is_false_positive:
                false_positives += 1

        return AnalysisStatistics(
            total_findings=len(findings),
            by_severity=by_severity,
            by_language=by_language,
            by_cwe=by_cwe,
            false_positives_filtered=false_positives,
        )
