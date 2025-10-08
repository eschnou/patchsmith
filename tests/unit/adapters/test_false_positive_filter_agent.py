"""Tests for false positive filter agent."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from patchsmith.adapters.claude.agent import AgentError
from patchsmith.adapters.claude.false_positive_filter_agent import (
    FalsePositiveFilterAgent,
)
from patchsmith.models.finding import CWE, Finding, Severity


class TestFalsePositiveFilterAgent:
    """Tests for FalsePositiveFilterAgent."""

    def test_init(self, tmp_path: Path) -> None:
        """Test agent initialization."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)

        assert agent.working_dir == tmp_path
        assert agent.agent_name == "FalsePositiveFilterAgent"

    def test_get_system_prompt(self, tmp_path: Path) -> None:
        """Test system prompt generation."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        prompt = agent.get_system_prompt()

        assert "security analysis expert" in prompt.lower()
        assert "false positive" in prompt.lower()
        assert "JSON" in prompt
        assert "confidence" in prompt.lower()

    def test_build_analysis_prompt(self, tmp_path: Path) -> None:
        """Test analysis prompt building."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/sql-injection",
            message="Potential SQL injection",
            severity=Severity.HIGH,
            file_path=tmp_path / "test.py",
            start_line=10,
            end_line=10,
            cwe=CWE(id="CWE-89"),
            snippet="cursor.execute(query)",
        )

        prompt = agent._build_analysis_prompt(finding)

        assert "python/sql-injection" in prompt
        assert "Potential SQL injection" in prompt
        assert "CWE-89" in prompt
        assert "test.py" in prompt
        assert "cursor.execute(query)" in prompt

    def test_build_analysis_prompt_no_snippet(self, tmp_path: Path) -> None:
        """Test prompt building without code snippet."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test finding",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        prompt = agent._build_analysis_prompt(finding)

        assert "test.py" in prompt
        assert "Code snippet" not in prompt

    @pytest.mark.asyncio
    @patch.object(FalsePositiveFilterAgent, "query_claude")
    async def test_execute_success(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test successful false positive analysis."""
        mock_query.return_value = """
{
  "is_false_positive": true,
  "score": 0.85,
  "reasoning": "Input is properly sanitized"
}
"""

        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/sql-injection",
            message="SQL injection",
            severity=Severity.HIGH,
            file_path=tmp_path / "test.py",
            start_line=10,
            end_line=10,
        )

        results = await agent.execute([finding])

        assert len(results) == 1
        assert results[0].id == "test-1"
        assert results[0].false_positive_score is not None
        assert results[0].false_positive_score.is_false_positive is True
        assert results[0].false_positive_score.score == 0.85
        assert "sanitized" in results[0].false_positive_score.reasoning

    @pytest.mark.asyncio
    @patch.object(FalsePositiveFilterAgent, "query_claude")
    async def test_execute_not_false_positive(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test analysis identifying real vulnerability."""
        mock_query.return_value = """
{
  "is_false_positive": false,
  "score": 0.95,
  "reasoning": "No input validation found"
}
"""

        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/sql-injection",
            message="SQL injection",
            severity=Severity.CRITICAL,
            file_path=tmp_path / "test.py",
            start_line=20,
            end_line=20,
        )

        results = await agent.execute([finding])

        assert len(results) == 1
        assert results[0].false_positive_score is not None
        assert results[0].false_positive_score.is_false_positive is False
        assert results[0].false_positive_score.score == 0.95

    @pytest.mark.asyncio
    @patch.object(FalsePositiveFilterAgent, "query_claude")
    async def test_execute_multiple_findings(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test analyzing multiple findings."""
        # Return different responses for each finding
        mock_query.side_effect = [
            '{"is_false_positive": true, "score": 0.8, "reasoning": "Safe"}',
            '{"is_false_positive": false, "score": 0.9, "reasoning": "Unsafe"}',
        ]

        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        findings = [
            Finding(
                id="test-1",
                rule_id="rule-1",
                message="Finding 1",
                severity=Severity.MEDIUM,
                file_path=tmp_path / "test1.py",
                start_line=10,
                end_line=10,
            ),
            Finding(
                id="test-2",
                rule_id="rule-2",
                message="Finding 2",
                severity=Severity.HIGH,
                file_path=tmp_path / "test2.py",
                start_line=20,
                end_line=20,
            ),
        ]

        results = await agent.execute(findings)

        assert len(results) == 2
        assert results[0].false_positive_score.is_false_positive is True
        assert results[1].false_positive_score.is_false_positive is False

    @pytest.mark.asyncio
    @patch.object(FalsePositiveFilterAgent, "query_claude")
    async def test_execute_with_failure(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test handling individual finding analysis failures."""
        # First succeeds, second fails, third succeeds
        mock_query.side_effect = [
            '{"is_false_positive": true, "score": 0.8, "reasoning": "OK"}',
            Exception("API Error"),
            '{"is_false_positive": false, "score": 0.9, "reasoning": "Bad"}',
        ]

        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        findings = [
            Finding(
                id="test-1",
                rule_id="rule-1",
                message="Finding 1",
                severity=Severity.MEDIUM,
                file_path=tmp_path / "test1.py",
                start_line=10,
                end_line=10,
            ),
            Finding(
                id="test-2",
                rule_id="rule-2",
                message="Finding 2",
                severity=Severity.HIGH,
                file_path=tmp_path / "test2.py",
                start_line=20,
                end_line=20,
            ),
            Finding(
                id="test-3",
                rule_id="rule-3",
                message="Finding 3",
                severity=Severity.LOW,
                file_path=tmp_path / "test3.py",
                start_line=30,
                end_line=30,
            ),
        ]

        results = await agent.execute(findings)

        # All findings returned, but second one has no FP score
        assert len(results) == 3
        assert results[0].false_positive_score is not None
        assert results[1].false_positive_score is None  # Failed
        assert results[2].false_positive_score is not None

    def test_parse_response_success(self, tmp_path: Path) -> None:
        """Test successful response parsing."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        response = """
{
  "is_false_positive": true,
  "score": 0.92,
  "reasoning": "The code uses parameterized queries"
}
"""

        score = agent._parse_response(response)

        assert score.is_false_positive is True
        assert score.score == 0.92
        assert "parameterized" in score.reasoning

    def test_parse_response_low_score(self, tmp_path: Path) -> None:
        """Test parsing response with low score."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        response = """
{
  "is_false_positive": false,
  "score": 0.75,
  "reasoning": "No validation found"
}
"""

        score = agent._parse_response(response)

        assert score.is_false_positive is False
        assert score.score == 0.75

    def test_parse_response_no_json(self, tmp_path: Path) -> None:
        """Test parsing error when no JSON found."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        response = "No JSON here"

        with pytest.raises(AgentError, match="No JSON object found"):
            agent._parse_response(response)

    def test_parse_response_invalid_json(self, tmp_path: Path) -> None:
        """Test parsing error with invalid JSON."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        response = "{invalid json}"

        with pytest.raises(AgentError, match="Failed to parse JSON"):
            agent._parse_response(response)

    def test_parse_response_not_object(self, tmp_path: Path) -> None:
        """Test parsing error when JSON is not an object."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        response = '["array", "not", "object"]'

        with pytest.raises(AgentError, match="No JSON object found"):
            agent._parse_response(response)

    def test_parse_response_missing_fields(self, tmp_path: Path) -> None:
        """Test parsing error with missing required fields."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        response = '{"is_false_positive": true}'

        with pytest.raises(AgentError, match="Missing required fields"):
            agent._parse_response(response)

    def test_parse_response_type_conversion(self, tmp_path: Path) -> None:
        """Test type conversion in parsing."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)
        response = """
{
  "is_false_positive": 1,
  "score": "0.88",
  "reasoning": "Test"
}
"""

        score = agent._parse_response(response)

        assert score.is_false_positive is True  # 1 -> True
        assert score.score == 0.88  # "0.88" -> 0.88
        assert isinstance(score.reasoning, str)

    @pytest.mark.asyncio
    @patch.object(FalsePositiveFilterAgent, "query_claude")
    async def test_execute_empty_list(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test executing with empty findings list."""
        agent = FalsePositiveFilterAgent(working_dir=tmp_path)

        results = await agent.execute([])

        assert len(results) == 0
        mock_query.assert_not_called()
