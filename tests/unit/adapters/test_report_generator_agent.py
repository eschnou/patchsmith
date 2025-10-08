"""Tests for report generator agent."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from patchsmith.adapters.claude.agent import AgentError
from patchsmith.adapters.claude.report_generator_agent import ReportGeneratorAgent
from patchsmith.models.analysis import AnalysisResult, AnalysisStatistics
from patchsmith.models.finding import CWE, FalsePositiveScore, Finding, Severity


class TestReportGeneratorAgent:
    """Tests for ReportGeneratorAgent."""

    def test_init(self, tmp_path: Path) -> None:
        """Test agent initialization."""
        agent = ReportGeneratorAgent(working_dir=tmp_path)

        assert agent.working_dir == tmp_path
        assert agent.agent_name == "ReportGeneratorAgent"

    def test_get_system_prompt(self, tmp_path: Path) -> None:
        """Test system prompt generation."""
        agent = ReportGeneratorAgent(working_dir=tmp_path)
        prompt = agent.get_system_prompt()

        assert "security report" in prompt.lower()
        assert "Executive Summary" in prompt
        assert "Recommendations" in prompt

    def test_format_finding(self, tmp_path: Path) -> None:
        """Test finding formatting."""
        agent = ReportGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/sql-injection",
            message="SQL injection vulnerability",
            severity=Severity.HIGH,
            file_path=tmp_path / "test.py",
            start_line=10,
            end_line=10,
            cwe=CWE(id="CWE-89"),
        )

        formatted = agent._format_finding(finding, 1)

        assert "Finding #1" in formatted
        assert "python/sql-injection" in formatted
        assert "HIGH" in formatted
        assert "CWE-89" in formatted
        assert "SQL injection" in formatted

    def test_format_finding_with_false_positive(self, tmp_path: Path) -> None:
        """Test formatting finding with false positive score."""
        agent = ReportGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test finding",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
            false_positive_score=FalsePositiveScore(
                is_false_positive=True,
                score=0.85,
                reasoning="Sanitized input",
            ),
        )

        formatted = agent._format_finding(finding, 2)

        assert "Finding #2" in formatted
        assert "Likely FP" in formatted
        assert "0.85" in formatted

    def test_build_generation_prompt(self, tmp_path: Path) -> None:
        """Test generation prompt building."""
        agent = ReportGeneratorAgent(working_dir=tmp_path)

        findings = [
            Finding(
                id="test-1",
                rule_id="python/sql-injection",
                message="SQL injection",
                severity=Severity.CRITICAL,
                file_path=tmp_path / "test.py",
                start_line=10,
                end_line=10,
            ),
        ]

        analysis = AnalysisResult(
            project_name="Test Project",
            languages_analyzed=["python"],
            findings=findings,
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            statistics=AnalysisStatistics(
                total_findings=1,
                by_severity={Severity.CRITICAL: 1},
            ),
        )

        prompt = agent._build_generation_prompt(analysis, findings, "markdown")

        assert "Total findings: 1" in prompt
        assert "Critical: 1" in prompt
        assert "python/sql-injection" in prompt
        assert "Markdown" in prompt

    def test_build_generation_prompt_many_findings(self, tmp_path: Path) -> None:
        """Test prompt with more than 10 findings."""
        agent = ReportGeneratorAgent(working_dir=tmp_path)

        findings = [
            Finding(
                id=f"test-{i}",
                rule_id=f"rule-{i}",
                message=f"Finding {i}",
                severity=Severity.MEDIUM,
                file_path=tmp_path / f"test{i}.py",
                start_line=i + 1,  # Lines must be >= 1
                end_line=i + 1,
            )
            for i in range(15)
        ]

        analysis = AnalysisResult(
            project_name="Test Project",
            languages_analyzed=["python"],
            findings=findings,
            timestamp=datetime.now(timezone.utc),
            statistics=AnalysisStatistics(
                total_findings=15,
                by_severity={Severity.MEDIUM: 15},
            ),
        )

        prompt = agent._build_generation_prompt(analysis, findings, "markdown")

        assert "and 5 more findings" in prompt
        assert "Total findings: 15" in prompt

    @pytest.mark.asyncio
    @patch.object(ReportGeneratorAgent, "query_claude")
    async def test_execute_success(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test successful report generation."""
        mock_query.return_value = """# Security Analysis Report

## Executive Summary

Found 2 critical security vulnerabilities...

## Findings
..."""

        agent = ReportGeneratorAgent(working_dir=tmp_path)
        findings = [
            Finding(
                id="test-1",
                rule_id="python/sql-injection",
                message="SQL injection",
                severity=Severity.CRITICAL,
                file_path=tmp_path / "test.py",
                start_line=10,
                end_line=10,
            ),
        ]

        analysis = AnalysisResult(
            project_name="Test Project",
            languages_analyzed=["python"],
            findings=findings,
            timestamp=datetime.now(timezone.utc),
            statistics=AnalysisStatistics(
                total_findings=1,
                by_severity={Severity.CRITICAL: 1},
            ),
        )

        report = await agent.execute(analysis)

        assert "Security Analysis Report" in report
        assert "Executive Summary" in report
        mock_query.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(ReportGeneratorAgent, "query_claude")
    async def test_execute_filter_false_positives(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test filtering false positives from report."""
        mock_query.return_value = "# Report\n\nNo critical issues."

        agent = ReportGeneratorAgent(working_dir=tmp_path)
        findings = [
            Finding(
                id="test-1",
                rule_id="rule-1",
                message="Real issue",
                severity=Severity.HIGH,
                file_path=tmp_path / "test1.py",
                start_line=10,
                end_line=10,
            ),
            Finding(
                id="test-2",
                rule_id="rule-2",
                message="False positive",
                severity=Severity.HIGH,
                file_path=tmp_path / "test2.py",
                start_line=20,
                end_line=20,
                false_positive_score=FalsePositiveScore(
                    is_false_positive=True,
                    score=0.9,
                    reasoning="Safe",
                ),
            ),
        ]

        analysis = AnalysisResult(
            project_name="Test Project",
            languages_analyzed=["python"],
            findings=findings,
            timestamp=datetime.now(timezone.utc),
            statistics=AnalysisStatistics(
                total_findings=2,
                by_severity={Severity.HIGH: 2},
            ),
        )

        await agent.execute(analysis, include_false_positives=False)

        # Verify prompt contains only 1 finding (filtered)
        call_args = mock_query.call_args
        prompt = call_args.kwargs["prompt"]
        assert "Total findings: 1 (of 2 total)" in prompt

    @pytest.mark.asyncio
    @patch.object(ReportGeneratorAgent, "query_claude")
    async def test_execute_include_false_positives(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test including false positives in report."""
        mock_query.return_value = "# Report"

        agent = ReportGeneratorAgent(working_dir=tmp_path)
        findings = [
            Finding(
                id="test-1",
                rule_id="rule-1",
                message="Issue",
                severity=Severity.HIGH,
                file_path=tmp_path / "test.py",
                start_line=10,
                end_line=10,
                false_positive_score=FalsePositiveScore(
                    is_false_positive=True,
                    score=0.8,
                    reasoning="Maybe safe",
                ),
            ),
        ]

        analysis = AnalysisResult(
            project_name="Test Project",
            languages_analyzed=["python"],
            findings=findings,
            timestamp=datetime.now(timezone.utc),
            statistics=AnalysisStatistics(
                total_findings=1,
                by_severity={Severity.HIGH: 1},
            ),
        )

        await agent.execute(analysis, include_false_positives=True)

        # Verify prompt contains the finding
        call_args = mock_query.call_args
        prompt = call_args.kwargs["prompt"]
        assert "Total findings: 1 (of 1 total)" in prompt

    @pytest.mark.asyncio
    @patch.object(ReportGeneratorAgent, "query_claude")
    async def test_execute_different_formats(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test report generation with different formats."""
        mock_query.return_value = "Report content"

        agent = ReportGeneratorAgent(working_dir=tmp_path)
        analysis = AnalysisResult(
            project_name="Test Project",
            languages_analyzed=[],
            findings=[],
            timestamp=datetime.now(timezone.utc),
            statistics=AnalysisStatistics(total_findings=0),
        )

        # Test markdown
        await agent.execute(analysis, report_format="markdown")
        prompt = mock_query.call_args.kwargs["prompt"]
        assert "Markdown" in prompt

        # Test HTML
        await agent.execute(analysis, report_format="html")
        prompt = mock_query.call_args.kwargs["prompt"]
        assert "HTML" in prompt

        # Test text (no special format instruction)
        await agent.execute(analysis, report_format="text")
        prompt = mock_query.call_args.kwargs["prompt"]
        assert "Markdown" not in prompt
        assert "HTML" not in prompt

    @pytest.mark.asyncio
    @patch.object(ReportGeneratorAgent, "query_claude")
    async def test_execute_error(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test error handling."""
        mock_query.side_effect = Exception("API Error")

        agent = ReportGeneratorAgent(working_dir=tmp_path)
        analysis = AnalysisResult(
            project_name="Test Project",
            languages_analyzed=[],
            findings=[],
            timestamp=datetime.now(timezone.utc),
            statistics=AnalysisStatistics(total_findings=0),
        )

        with pytest.raises(AgentError, match="Report generation failed"):
            await agent.execute(analysis)
