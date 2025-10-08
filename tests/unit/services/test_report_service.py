"""Tests for ReportService class."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patchsmith.models.analysis import AnalysisResult, AnalysisStatistics
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import Severity
from patchsmith.services.report_service import ReportService


class TestReportService:
    """Test ReportService functionality."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> PatchsmithConfig:
        """Create test configuration."""
        return PatchsmithConfig.create_default(project_root=tmp_path)

    @pytest.fixture
    def service(self, config: PatchsmithConfig) -> ReportService:
        """Create ReportService instance."""
        return ReportService(config=config)

    @pytest.fixture
    def mock_analysis_result(self) -> AnalysisResult:
        """Create a mock analysis result."""
        return AnalysisResult(
            project_name="test-project",
            findings=[],
            statistics=AnalysisStatistics(
                total_findings=10,
                by_severity={Severity.HIGH: 5, Severity.MEDIUM: 5},
                by_language={},
                by_cwe={},
                false_positives_filtered=0,
            ),
            timestamp=datetime.now(),
            languages_analyzed=["python"],
        )

    def test_init(self, config: PatchsmithConfig) -> None:
        """Test service initialization."""
        service = ReportService(config=config)

        assert service.config == config
        assert service.service_name == "ReportService"

    def test_init_with_callback(self, config: PatchsmithConfig) -> None:
        """Test service initialization with progress callback."""
        callback = MagicMock()
        service = ReportService(config=config, progress_callback=callback)

        assert service.progress_callback == callback

    @pytest.mark.asyncio
    async def test_generate_report_markdown(
        self,
        service: ReportService,
        mock_analysis_result: AnalysisResult,
    ) -> None:
        """Test generating markdown report."""
        with patch(
            "patchsmith.services.report_service.ReportGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = "# Security Report\n\nFindings: 10"
            mock_agent.return_value = mock_instance

            report = await service.generate_report(
                analysis_result=mock_analysis_result,
                report_format="markdown",
            )

            assert report == "# Security Report\n\nFindings: 10"
            mock_agent.assert_called_once()
            mock_instance.execute.assert_called_once_with(
                analysis_result=mock_analysis_result,
                triage_results=None,
                detailed_assessments=None,
                report_format="markdown",
            )

    @pytest.mark.asyncio
    async def test_generate_report_with_triage(
        self,
        service: ReportService,
        mock_analysis_result: AnalysisResult,
    ) -> None:
        """Test generating report with triage results."""
        from patchsmith.models.analysis import TriageResult

        triage_results = [
            TriageResult(
                finding_id="test-1",
                priority_score=0.95,
                reasoning="Critical issue",
                recommended_for_analysis=True,
            )
        ]

        with patch(
            "patchsmith.services.report_service.ReportGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = "# Report with triage"
            mock_agent.return_value = mock_instance

            report = await service.generate_report(
                analysis_result=mock_analysis_result,
                triage_results=triage_results,
                report_format="markdown",
            )

            assert report == "# Report with triage"
            mock_instance.execute.assert_called_once_with(
                analysis_result=mock_analysis_result,
                triage_results=triage_results,
                detailed_assessments=None,
                report_format="markdown",
            )

    @pytest.mark.asyncio
    async def test_generate_report_with_detailed_assessments(
        self,
        service: ReportService,
        mock_analysis_result: AnalysisResult,
    ) -> None:
        """Test generating report with detailed assessments."""
        from patchsmith.models.finding import DetailedSecurityAssessment, RiskType

        detailed_assessments = {
            "test-1": DetailedSecurityAssessment(
                finding_id="test-1",
                is_false_positive=False,
                false_positive_score=0.1,
                false_positive_reasoning="Confirmed",
                attack_scenario="SQL injection",
                risk_type=RiskType.EXTERNAL_PENTEST,
                exploitability_score=0.9,
                impact_description="Database compromise",
                remediation_priority="immediate",
            )
        }

        with patch(
            "patchsmith.services.report_service.ReportGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = "# Report with assessments"
            mock_agent.return_value = mock_instance

            report = await service.generate_report(
                analysis_result=mock_analysis_result,
                detailed_assessments=detailed_assessments,
                report_format="markdown",
            )

            assert report == "# Report with assessments"
            mock_instance.execute.assert_called_once_with(
                analysis_result=mock_analysis_result,
                triage_results=None,
                detailed_assessments=detailed_assessments,
                report_format="markdown",
            )

    @pytest.mark.asyncio
    async def test_generate_report_save_to_file(
        self,
        service: ReportService,
        mock_analysis_result: AnalysisResult,
        tmp_path: Path,
    ) -> None:
        """Test saving report to file."""
        output_path = tmp_path / "reports" / "security-report.md"

        with patch(
            "patchsmith.services.report_service.ReportGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = "# Security Report"
            mock_agent.return_value = mock_instance

            report = await service.generate_report(
                analysis_result=mock_analysis_result,
                report_format="markdown",
                output_path=output_path,
            )

            assert report == "# Security Report"
            assert output_path.exists()
            assert output_path.read_text() == "# Security Report"

    @pytest.mark.asyncio
    async def test_generate_report_progress_callbacks(
        self,
        config: PatchsmithConfig,
        mock_analysis_result: AnalysisResult,
    ) -> None:
        """Test that progress callbacks are emitted."""
        callback = MagicMock()
        service = ReportService(config=config, progress_callback=callback)

        with patch(
            "patchsmith.services.report_service.ReportGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = "# Report"
            mock_agent.return_value = mock_instance

            await service.generate_report(
                analysis_result=mock_analysis_result,
                report_format="markdown",
            )

            callback_events = [call[0][0] for call in callback.call_args_list]
            assert "report_generation_started" in callback_events
            assert "report_generation_completed" in callback_events

    @pytest.mark.asyncio
    async def test_generate_report_progress_callbacks_with_save(
        self,
        config: PatchsmithConfig,
        mock_analysis_result: AnalysisResult,
        tmp_path: Path,
    ) -> None:
        """Test progress callbacks when saving to file."""
        callback = MagicMock()
        service = ReportService(config=config, progress_callback=callback)
        output_path = tmp_path / "report.md"

        with patch(
            "patchsmith.services.report_service.ReportGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = "# Report"
            mock_agent.return_value = mock_instance

            await service.generate_report(
                analysis_result=mock_analysis_result,
                report_format="markdown",
                output_path=output_path,
            )

            callback_events = [call[0][0] for call in callback.call_args_list]
            assert "report_saving" in callback_events
            assert "report_saved" in callback_events

    @pytest.mark.asyncio
    async def test_generate_report_error_handling(
        self,
        config: PatchsmithConfig,
        mock_analysis_result: AnalysisResult,
    ) -> None:
        """Test error handling during report generation."""
        callback = MagicMock()
        service = ReportService(config=config, progress_callback=callback)

        with patch(
            "patchsmith.services.report_service.ReportGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.side_effect = Exception("Report generation failed")
            mock_agent.return_value = mock_instance

            with pytest.raises(Exception, match="Report generation failed"):
                await service.generate_report(
                    analysis_result=mock_analysis_result,
                    report_format="markdown",
                )

            callback_events = [call[0][0] for call in callback.call_args_list]
            assert "report_generation_failed" in callback_events

    @pytest.mark.asyncio
    async def test_generate_report_different_formats(
        self,
        service: ReportService,
        mock_analysis_result: AnalysisResult,
    ) -> None:
        """Test generating reports in different formats."""
        with patch(
            "patchsmith.services.report_service.ReportGeneratorAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()

            # Test HTML format
            mock_instance.execute.return_value = "<html>Report</html>"
            mock_agent.return_value = mock_instance

            html_report = await service.generate_report(
                analysis_result=mock_analysis_result,
                report_format="html",
            )

            assert html_report == "<html>Report</html>"
            mock_instance.execute.assert_called_with(
                analysis_result=mock_analysis_result,
                triage_results=None,
                detailed_assessments=None,
                report_format="html",
            )

            # Test text format
            mock_instance.execute.return_value = "Plain text report"
            await service.generate_report(
                analysis_result=mock_analysis_result,
                report_format="text",
            )

            mock_instance.execute.assert_called_with(
                analysis_result=mock_analysis_result,
                triage_results=None,
                detailed_assessments=None,
                report_format="text",
            )
