"""Report service for generating security analysis reports."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from patchsmith.adapters.claude.report_generator_agent import ReportGeneratorAgent
from patchsmith.models.analysis import AnalysisResult, TriageResult
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import DetailedSecurityAssessment
from patchsmith.presentation.formatters.report_base import BaseReportFormatter
from patchsmith.presentation.formatters.report_html import ReportHtmlFormatter
from patchsmith.presentation.formatters.report_markdown import ReportMarkdownFormatter
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
        thinking_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Initialize report service.

        Args:
            config: Patchsmith configuration
            progress_callback: Optional progress callback
            thinking_callback: Optional callback for agent thinking updates
        """
        super().__init__(config, progress_callback)
        self.thinking_callback = thinking_callback

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
            report_format: Output format ("markdown", "html")
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
            # Create agent progress callback
            def agent_progress_callback(current_turn: int, max_turns: int) -> None:
                self._emit_progress(
                    "agent_turn_progress",
                    current_turn=current_turn,
                    max_turns=max_turns,
                )

            # Initialize report generator agent
            report_agent = ReportGeneratorAgent(
                working_dir=Path.cwd(),
                thinking_callback=self.thinking_callback,
                progress_callback=agent_progress_callback,
            )

            # Generate structured report data
            report_data = await report_agent.execute(
                analysis_result=analysis_result,
                triage_results=triage_results,
                detailed_assessments=detailed_assessments,
            )

            # Clear thinking display when agent completes
            if self.thinking_callback:
                self.thinking_callback("")

            self._emit_progress(
                "report_formatting_started",
                format=report_format,
            )

            # Select appropriate formatter
            formatter = self._get_formatter(report_format)

            # Format the report
            formatted_report = formatter.format(report_data)

            self._emit_progress(
                "report_generation_completed",
                report_length=len(formatted_report),
            )

            # Save to file if path provided
            if output_path:
                self._emit_progress("report_saving", path=str(output_path))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(formatted_report)
                self._emit_progress("report_saved", path=str(output_path))

            return formatted_report

        except Exception as e:
            self._emit_progress("report_generation_failed", error=str(e))
            logger.error(
                "report_service_error",
                project=analysis_result.project_name,
                error=str(e),
            )
            raise

    def _get_formatter(self, report_format: str) -> BaseReportFormatter:
        """
        Get the appropriate formatter for the specified format.

        Args:
            report_format: Desired format (markdown, html)

        Returns:
            Formatter instance

        Raises:
            ValueError: If format is not supported
        """
        formatters = {
            "markdown": ReportMarkdownFormatter(),
            "html": ReportHtmlFormatter(),
        }

        formatter = formatters.get(report_format.lower())
        if formatter is None:
            raise ValueError(
                f"Unsupported report format: {report_format}. "
                f"Supported formats: {', '.join(formatters.keys())}"
            )

        return formatter
