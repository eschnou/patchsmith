"""Tests for AnalysisService class."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patchsmith.models.analysis import AnalysisResult, AnalysisStatistics, TriageResult
from patchsmith.models.config import PatchsmithConfig
from patchsmith.models.finding import (
    CWE,
    DetailedSecurityAssessment,
    Finding,
    RiskType,
    Severity,
)
from patchsmith.models.project import LanguageDetection
from patchsmith.services.analysis_service import AnalysisService


class TestAnalysisService:
    """Test AnalysisService functionality."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> PatchsmithConfig:
        """Create test configuration."""
        return PatchsmithConfig.create_default(project_root=tmp_path)

    @pytest.fixture
    def service(self, config: PatchsmithConfig) -> AnalysisService:
        """Create AnalysisService instance."""
        return AnalysisService(config=config)

    @pytest.fixture
    def mock_finding(self, tmp_path: Path) -> Finding:
        """Create a mock finding."""
        return Finding(
            id="test-finding-1",
            rule_id="test-rule",
            message="Test vulnerability",
            severity=Severity.HIGH,
            file_path=tmp_path / "test.py",
            start_line=10,
            end_line=12,
            snippet="vulnerable code",
            cwe=CWE(id="CWE-89", name="SQL Injection"),
        )

    @pytest.fixture
    def mock_triage_result(self) -> TriageResult:
        """Create a mock triage result."""
        return TriageResult(
            finding_id="test-finding-1",
            priority_score=0.95,
            reasoning="Critical SQL injection",
            recommended_for_analysis=True,
        )

    @pytest.fixture
    def mock_detailed_assessment(self) -> DetailedSecurityAssessment:
        """Create a mock detailed assessment."""
        return DetailedSecurityAssessment(
            finding_id="test-finding-1",
            is_false_positive=False,
            false_positive_score=0.1,
            false_positive_reasoning="Confirmed vulnerability",
            attack_scenario="Attacker can inject SQL",
            risk_type=RiskType.EXTERNAL_PENTEST,
            exploitability_score=0.9,
            impact_description="Database compromise",
            remediation_priority="immediate",
        )

    def test_init(self, config: PatchsmithConfig) -> None:
        """Test service initialization."""
        service = AnalysisService(config=config)

        assert service.config == config
        assert service.codeql is not None
        assert service.sarif_parser is not None

    def test_init_with_callback(self, config: PatchsmithConfig) -> None:
        """Test service initialization with progress callback."""
        callback = MagicMock()
        service = AnalysisService(config=config, progress_callback=callback)

        assert service.progress_callback == callback

    def test_map_language_to_codeql(self, service: AnalysisService) -> None:
        """Test language mapping to CodeQL."""
        assert service._map_language_to_codeql("python") == "python"
        assert service._map_language_to_codeql("Python") == "python"
        assert service._map_language_to_codeql("javascript") == "javascript"
        assert service._map_language_to_codeql("typescript") == "javascript"
        assert service._map_language_to_codeql("java") == "java"
        assert service._map_language_to_codeql("go") == "go"
        assert service._map_language_to_codeql("cpp") == "cpp"
        assert service._map_language_to_codeql("c") == "cpp"
        assert service._map_language_to_codeql("csharp") == "csharp"
        assert service._map_language_to_codeql("ruby") == "ruby"
        assert service._map_language_to_codeql("unknown") == "unknown"

    def test_get_query_suite(self, service: AnalysisService) -> None:
        """Test query suite selection."""
        assert (
            service._get_query_suite("python")
            == "codeql/python-queries:codeql-suites/python-security-and-quality.qls"
        )
        assert (
            service._get_query_suite("javascript")
            == "codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls"
        )
        assert (
            service._get_query_suite("java")
            == "codeql/java-queries:codeql-suites/java-security-and-quality.qls"
        )
        assert (
            service._get_query_suite("unknown")
            == "codeql/unknown-queries"
        )

    def test_compute_statistics(
        self, service: AnalysisService, mock_finding: Finding
    ) -> None:
        """Test statistics computation."""
        findings = [
            mock_finding,
            Finding(
                id="test-finding-2",
                rule_id="test-rule-2",
                message="Another vulnerability",
                severity=Severity.MEDIUM,
                file_path=mock_finding.file_path,
                start_line=20,
                end_line=22,
                snippet="another vulnerable code",
            ),
        ]

        stats = service._compute_statistics(findings)

        assert isinstance(stats, AnalysisStatistics)
        assert stats.total_findings == 2
        assert stats.by_severity[Severity.HIGH] == 1
        assert stats.by_severity[Severity.MEDIUM] == 1
        assert stats.by_cwe["CWE-89"] == 1
        assert stats.false_positives_filtered == 0

    def test_compute_statistics_with_false_positives(
        self, service: AnalysisService, tmp_path: Path
    ) -> None:
        """Test statistics computation with false positives."""
        from patchsmith.models.finding import FalsePositiveScore

        findings = [
            Finding(
                id="fp-1",
                rule_id="test-rule",
                message="False positive",
                severity=Severity.LOW,
                file_path=tmp_path / "test.py",
                start_line=1,
                end_line=1,
                false_positive_score=FalsePositiveScore(
                    score=0.9,
                    reasoning="Likely false positive",
                    is_false_positive=True,
                ),
            ),
        ]

        stats = service._compute_statistics(findings)

        assert stats.total_findings == 1
        assert stats.false_positives_filtered == 1

    @pytest.mark.asyncio
    async def test_analyze_project_no_languages_detected(
        self, service: AnalysisService, tmp_path: Path
    ) -> None:
        """Test analysis when no languages are detected."""
        with patch(
            "patchsmith.services.analysis_service.LanguageDetectionAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = []
            mock_agent.return_value = mock_instance

            with pytest.raises(ValueError, match="No languages detected"):
                await service.analyze_project(tmp_path)

    @pytest.mark.asyncio
    async def test_analyze_project_progress_callbacks(
        self, config: PatchsmithConfig, tmp_path: Path, mock_finding: Finding
    ) -> None:
        """Test that progress callbacks are emitted during analysis."""
        callback = MagicMock()
        service = AnalysisService(config=config, progress_callback=callback)

        # Mock all the adapters and agents
        with (
            patch("patchsmith.services.analysis_service.LanguageDetectionAgent") as mock_lang_agent,
            patch.object(service.codeql, "create_database") as mock_create_db,
            patch.object(service.codeql, "run_queries") as mock_run_queries,
            patch.object(service.sarif_parser, "parse_file") as mock_parse,
            patch("patchsmith.services.analysis_service.TriageAgent") as mock_triage_agent,
        ):
            # Setup mocks
            mock_lang_instance = AsyncMock()
            mock_lang_instance.execute.return_value = [
                LanguageDetection(name="python", confidence=0.95)
            ]
            mock_lang_agent.return_value = mock_lang_instance

            mock_parse.return_value = [mock_finding]

            mock_triage_instance = AsyncMock()
            mock_triage_instance.execute.return_value = []
            mock_triage_agent.return_value = mock_triage_instance

            # Run analysis
            await service.analyze_project(
                tmp_path,
                perform_triage=False,
                perform_detailed_analysis=False,
            )

            # Verify progress callbacks were called
            callback_events = [call[0][0] for call in callback.call_args_list]
            assert "analysis_started" in callback_events
            assert "language_detection_started" in callback_events
            assert "language_detection_completed" in callback_events
            assert "codeql_database_creation_started" in callback_events
            assert "codeql_database_created" in callback_events
            assert "codeql_queries_started" in callback_events
            assert "codeql_queries_completed" in callback_events
            assert "sarif_parsing_started" in callback_events
            assert "sarif_parsing_completed" in callback_events
            assert "statistics_computation_started" in callback_events
            assert "statistics_computation_completed" in callback_events
            assert "analysis_completed" in callback_events

    @pytest.mark.asyncio
    async def test_analyze_project_with_triage(
        self,
        config: PatchsmithConfig,
        tmp_path: Path,
        mock_finding: Finding,
        mock_triage_result: TriageResult,
    ) -> None:
        """Test analysis with triage enabled."""
        service = AnalysisService(config=config)

        with (
            patch("patchsmith.services.analysis_service.LanguageDetectionAgent") as mock_lang_agent,
            patch.object(service.codeql, "create_database"),
            patch.object(service.codeql, "run_queries"),
            patch.object(service.sarif_parser, "parse_file") as mock_parse,
            patch("patchsmith.services.analysis_service.TriageAgent") as mock_triage_agent,
        ):
            # Setup mocks
            mock_lang_instance = AsyncMock()
            mock_lang_instance.execute.return_value = [
                LanguageDetection(name="python", confidence=0.95)
            ]
            mock_lang_agent.return_value = mock_lang_instance

            mock_parse.return_value = [mock_finding]

            mock_triage_instance = AsyncMock()
            mock_triage_instance.execute.return_value = [mock_triage_result]
            mock_triage_agent.return_value = mock_triage_instance

            # Run analysis
            result, triage_results, detailed_assessments = await service.analyze_project(
                tmp_path,
                perform_triage=True,
                perform_detailed_analysis=False,
            )

            assert isinstance(result, AnalysisResult)
            assert triage_results == [mock_triage_result]
            assert detailed_assessments is None

    @pytest.mark.asyncio
    async def test_analyze_project_with_detailed_analysis(
        self,
        config: PatchsmithConfig,
        tmp_path: Path,
        mock_finding: Finding,
        mock_triage_result: TriageResult,
        mock_detailed_assessment: DetailedSecurityAssessment,
    ) -> None:
        """Test analysis with detailed analysis enabled."""
        service = AnalysisService(config=config)

        with (
            patch("patchsmith.services.analysis_service.LanguageDetectionAgent") as mock_lang_agent,
            patch.object(service.codeql, "create_database"),
            patch.object(service.codeql, "run_queries"),
            patch.object(service.sarif_parser, "parse_file") as mock_parse,
            patch("patchsmith.services.analysis_service.TriageAgent") as mock_triage_agent,
            patch("patchsmith.services.analysis_service.DetailedSecurityAnalysisAgent") as mock_analysis_agent,
        ):
            # Setup mocks
            mock_lang_instance = AsyncMock()
            mock_lang_instance.execute.return_value = [
                LanguageDetection(name="python", confidence=0.95)
            ]
            mock_lang_agent.return_value = mock_lang_instance

            mock_parse.return_value = [mock_finding]

            mock_triage_instance = AsyncMock()
            mock_triage_instance.execute.return_value = [mock_triage_result]
            mock_triage_agent.return_value = mock_triage_instance

            mock_analysis_instance = AsyncMock()
            mock_analysis_instance.execute.return_value = {
                "test-finding-1": mock_detailed_assessment
            }
            mock_analysis_agent.return_value = mock_analysis_instance

            # Run analysis
            result, triage_results, detailed_assessments = await service.analyze_project(
                tmp_path,
                perform_triage=True,
                perform_detailed_analysis=True,
                detailed_analysis_limit=10,
            )

            assert isinstance(result, AnalysisResult)
            assert triage_results == [mock_triage_result]
            assert detailed_assessments == {"test-finding-1": mock_detailed_assessment}

    @pytest.mark.asyncio
    async def test_analyze_project_error_handling(
        self, config: PatchsmithConfig, tmp_path: Path
    ) -> None:
        """Test error handling during analysis."""
        callback = MagicMock()
        service = AnalysisService(config=config, progress_callback=callback)

        with patch(
            "patchsmith.services.analysis_service.LanguageDetectionAgent"
        ) as mock_agent:
            mock_instance = AsyncMock()
            mock_instance.execute.side_effect = Exception("Language detection failed")
            mock_agent.return_value = mock_instance

            with pytest.raises(Exception, match="Language detection failed"):
                await service.analyze_project(tmp_path)

            # Verify error progress was emitted
            callback_events = [call[0][0] for call in callback.call_args_list]
            assert "analysis_failed" in callback_events
