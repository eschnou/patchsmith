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
    ) -> None:
        """
        Initialize analysis service.

        Args:
            config: Patchsmith configuration
            progress_callback: Optional progress callback
        """
        super().__init__(config, progress_callback)

        # Initialize adapters
        # CodeQL CLI path defaults to "codeql" (assumes it's in PATH)
        self.codeql = CodeQLCLI()
        self.sarif_parser = SARIFParser()

    async def analyze_project(
        self,
        project_path: Path,
        perform_triage: bool = True,
        perform_detailed_analysis: bool = True,
        detailed_analysis_limit: int = 10,
    ) -> tuple[AnalysisResult, list[TriageResult] | None, dict[str, DetailedSecurityAssessment] | None]:
        """
        Perform complete security analysis on a project.

        Args:
            project_path: Path to project to analyze
            perform_triage: Whether to perform triage (prioritization)
            perform_detailed_analysis: Whether to perform detailed analysis on top findings
            detailed_analysis_limit: Max findings to analyze in detail

        Returns:
            Tuple of (AnalysisResult, triage_results, detailed_assessments)

        Raises:
            Exception: If analysis fails at any stage
        """
        self._emit_progress("analysis_started", project_path=str(project_path))

        try:
            # Step 1: Detect languages
            self._emit_progress("language_detection_started")
            language_agent = LanguageDetectionAgent(
                working_dir=project_path,
            )
            languages = await language_agent.execute(project_path=project_path)
            self._emit_progress(
                "language_detection_completed",
                languages=[lang.name for lang in languages],
                count=len(languages),
            )

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
            db_path = project_path.parent / f".patchsmith_db_{codeql_language}"

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

            # Step 3: Run CodeQL queries
            self._emit_progress("codeql_queries_started")
            query_suite = self._get_query_suite(codeql_language)
            results_path = project_path.parent / f".patchsmith_results_{codeql_language}.sarif"

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

            # Step 4: Parse SARIF results
            self._emit_progress("sarif_parsing_started")
            findings = self.sarif_parser.parse_file(results_path)
            self._emit_progress(
                "sarif_parsing_completed",
                finding_count=len(findings),
            )

            # Step 5: Triage (optional)
            triage_results = None
            if perform_triage and len(findings) > 0:
                self._emit_progress("triage_started", finding_count=len(findings))
                triage_agent = TriageAgent(
                    working_dir=project_path,
                )
                # Use max_results from config, or default to 50 for triage
                max_findings = self.config.analysis.max_results if self.config.analysis.max_results else 50
                triage_results = await triage_agent.execute(
                    findings=findings,
                    top_n=max_findings,
                )
                recommended_count = sum(1 for t in triage_results if t.recommended_for_analysis)
                self._emit_progress(
                    "triage_completed",
                    prioritized_count=len(triage_results),
                    recommended_count=recommended_count,
                )

            # Step 6: Detailed security analysis (optional)
            detailed_assessments = None
            if perform_detailed_analysis and triage_results:
                # Get top findings recommended for analysis
                findings_to_analyze = []
                recommended = [t for t in triage_results if t.recommended_for_analysis]

                for triage in recommended[:detailed_analysis_limit]:
                    finding = next((f for f in findings if f.id == triage.finding_id), None)
                    if finding:
                        findings_to_analyze.append(finding)

                if findings_to_analyze:
                    self._emit_progress(
                        "detailed_analysis_started",
                        finding_count=len(findings_to_analyze),
                    )
                    analysis_agent = DetailedSecurityAnalysisAgent(
                        working_dir=project_path,
                    )
                    detailed_assessments = await analysis_agent.execute(findings_to_analyze)
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
