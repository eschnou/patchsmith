"""Report service for generating security analysis reports."""

from pathlib import Path
from typing import Any, Callable

from patchsmith.adapters.claude.report_generator_agent import ReportGeneratorAgent
from patchsmith.models.analysis import AnalysisResult, TriageResult
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import DetailedSecurityAssessment
from patchsmith.services.base_service import BaseService
from patchsmith.utils.logging import get_logger

logger = get_logger()


class ReportService(BaseService):
    """Service for generating security analysis reports.

    This service takes analysis results and generates comprehensive reports
    in various formats (markdown, HTML, text).
    """

    def __init__(
        self,
        config: PatchsmithConfig,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        """
        Initialize report service.

        Args:
            config: Patchsmith configuration
            progress_callback: Optional progress callback
        """
        super().__init__(config, progress_callback)

    async def generate_report(
        self,
        analysis_result: AnalysisResult,
        triage_results: list[TriageResult] | None = None,
        detailed_assessments: dict[str, DetailedSecurityAssessment] | None = None,
        report_format: str = "markdown",
        output_path: Path | None = None,
    ) -> str:
        """
        Generate a security analysis report.

        Args:
            analysis_result: Analysis results
            triage_results: Optional triage results
            detailed_assessments: Optional detailed assessments
            report_format: Output format ("markdown", "html", "text")
            output_path: Optional path to save report

        Returns:
            Generated report as string

        Raises:
            Exception: If report generation fails
        """
        self._emit_progress(
            "report_generation_started",
            format=report_format,
            finding_count=len(analysis_result.findings),
        )

        try:
            # Initialize report generator agent
            # Note: AnalysisResult doesn't have project_path, using a temp path
            from pathlib import Path
            report_agent = ReportGeneratorAgent(
                working_dir=Path.cwd(),
            )

            # Generate report
            report = await report_agent.execute(
                analysis_result=analysis_result,
                triage_results=triage_results,
                detailed_assessments=detailed_assessments,
                report_format=report_format,
            )

            self._emit_progress(
                "report_generation_completed",
                report_length=len(report),
            )

            # Save to file if path provided
            if output_path:
                self._emit_progress("report_saving", path=str(output_path))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(report)
                self._emit_progress("report_saved", path=str(output_path))

            return report

        except Exception as e:
            self._emit_progress("report_generation_failed", error=str(e))
            logger.error(
                "report_service_error",
                project=analysis_result.project_name,
                error=str(e),
            )
            raise
