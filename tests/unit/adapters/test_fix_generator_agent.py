"""Tests for fix generator agent."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from patchsmith.adapters.claude.agent import AgentError
from patchsmith.adapters.claude.fix_generator_agent import Fix, FixGeneratorAgent
from patchsmith.models.finding import CWE, Finding, Severity


class TestFixGeneratorAgent:
    """Tests for FixGeneratorAgent."""

    def test_init(self, tmp_path: Path) -> None:
        """Test agent initialization."""
        agent = FixGeneratorAgent(working_dir=tmp_path)

        assert agent.working_dir == tmp_path
        assert agent.agent_name == "FixGeneratorAgent"

    def test_get_system_prompt(self, tmp_path: Path) -> None:
        """Test system prompt generation."""
        agent = FixGeneratorAgent(working_dir=tmp_path)
        prompt = agent.get_system_prompt()

        assert "security" in prompt.lower()
        assert "vulnerability" in prompt.lower()
        assert "JSON" in prompt
        assert "original_code" in prompt
        assert "fixed_code" in prompt

    def test_build_generation_prompt(self, tmp_path: Path) -> None:
        """Test generation prompt building."""
        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/sql-injection",
            message="SQL injection vulnerability",
            severity=Severity.HIGH,
            file_path=tmp_path / "test.py",
            start_line=10,
            end_line=10,
            cwe=CWE(id="CWE-89"),
            snippet="cursor.execute('SELECT * FROM users WHERE id=' + user_id)",
        )

        prompt = agent._build_generation_prompt(finding, context_lines=5)

        assert "python/sql-injection" in prompt
        assert "CWE-89" in prompt
        assert "cursor.execute" in prompt
        assert "test.py" in prompt
        assert "line 10" in prompt

    def test_build_generation_prompt_no_snippet(self, tmp_path: Path) -> None:
        """Test prompt building without code snippet."""
        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test finding",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        prompt = agent._build_generation_prompt(finding, context_lines=10)

        assert "test.py" in prompt
        assert "Vulnerable code" not in prompt

    @pytest.mark.asyncio
    @patch.object(FixGeneratorAgent, "query_claude")
    async def test_execute_success(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test successful fix generation."""
        mock_query.return_value = """
{
  "original_code": "cursor.execute('SELECT * FROM users WHERE id=' + user_id)",
  "fixed_code": "cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))",
  "explanation": "Use parameterized query to prevent SQL injection",
  "confidence": 0.95
}
"""

        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/sql-injection",
            message="SQL injection",
            severity=Severity.CRITICAL,
            file_path=tmp_path / "test.py",
            start_line=10,
            end_line=10,
        )

        fix = await agent.execute(finding)

        assert fix is not None
        assert fix.finding_id == "test-1"
        assert fix.file_path == tmp_path / "test.py"
        assert "parameterized" in fix.original_code or "SELECT" in fix.original_code
        assert "?" in fix.fixed_code or "parameterized" in fix.explanation.lower()
        assert fix.confidence == 0.95
        assert "parameterized" in fix.explanation.lower() or "injection" in fix.explanation.lower()

    @pytest.mark.asyncio
    @patch.object(FixGeneratorAgent, "query_claude")
    async def test_execute_low_confidence(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test handling low confidence fixes."""
        mock_query.return_value = """
{
  "original_code": "some code",
  "fixed_code": "some code",
  "explanation": "Cannot safely fix without more context",
  "confidence": 0.3
}
"""

        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/complex-issue",
            message="Complex issue",
            severity=Severity.HIGH,
            file_path=tmp_path / "test.py",
            start_line=10,
            end_line=10,
        )

        fix = await agent.execute(finding)

        # Low confidence should return None
        assert fix is None

    @pytest.mark.asyncio
    @patch.object(FixGeneratorAgent, "query_claude")
    async def test_execute_no_json(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test handling response with no JSON."""
        mock_query.return_value = "I cannot generate a fix for this issue."

        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        fix = await agent.execute(finding)

        assert fix is None

    @pytest.mark.asyncio
    @patch.object(FixGeneratorAgent, "query_claude")
    async def test_execute_missing_fields(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test handling response with missing fields."""
        mock_query.return_value = """
{
  "original_code": "some code",
  "explanation": "Some explanation"
}
"""

        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        fix = await agent.execute(finding)

        assert fix is None

    def test_parse_response_success(self, tmp_path: Path) -> None:
        """Test successful response parsing."""
        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/sql-injection",
            message="SQL injection",
            severity=Severity.HIGH,
            file_path=tmp_path / "test.py",
            start_line=10,
            end_line=10,
        )

        response = """
{
  "original_code": "execute('SELECT * FROM users WHERE id=' + uid)",
  "fixed_code": "execute('SELECT * FROM users WHERE id=?', (uid,))",
  "explanation": "Use parameterized queries to prevent SQL injection attacks",
  "confidence": 0.92
}
"""

        fix = agent._parse_response(response, finding)

        assert fix is not None
        assert fix.finding_id == "test-1"
        assert "SELECT" in fix.original_code
        assert "?" in fix.fixed_code
        assert fix.confidence == 0.92
        assert "parameterized" in fix.explanation.lower()

    def test_parse_response_low_confidence(self, tmp_path: Path) -> None:
        """Test parsing with low confidence returns None."""
        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        response = """
{
  "original_code": "code",
  "fixed_code": "code",
  "explanation": "Too complex to fix safely",
  "confidence": 0.2
}
"""

        fix = agent._parse_response(response, finding)

        assert fix is None

    def test_parse_response_no_json(self, tmp_path: Path) -> None:
        """Test parsing when no JSON found."""
        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        response = "No JSON here"

        fix = agent._parse_response(response, finding)

        assert fix is None

    def test_parse_response_invalid_json(self, tmp_path: Path) -> None:
        """Test parsing with invalid JSON."""
        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        response = "{invalid json}"

        fix = agent._parse_response(response, finding)

        assert fix is None

    def test_parse_response_not_object(self, tmp_path: Path) -> None:
        """Test parsing when JSON is not an object."""
        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        response = '["array", "not", "object"]'

        fix = agent._parse_response(response, finding)

        assert fix is None

    def test_parse_response_missing_fields(self, tmp_path: Path) -> None:
        """Test parsing with missing required fields."""
        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        response = '{"original_code": "code", "confidence": 0.9}'

        fix = agent._parse_response(response, finding)

        assert fix is None

    @pytest.mark.asyncio
    @patch.object(FixGeneratorAgent, "query_claude")
    async def test_execute_error(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test error handling."""
        mock_query.side_effect = Exception("API Error")

        agent = FixGeneratorAgent(working_dir=tmp_path)
        finding = Finding(
            id="test-1",
            rule_id="python/test",
            message="Test",
            severity=Severity.MEDIUM,
            file_path=tmp_path / "test.py",
            start_line=5,
            end_line=5,
        )

        with pytest.raises(AgentError, match="Fix generation failed"):
            await agent.execute(finding)

    def test_fix_model(self, tmp_path: Path) -> None:
        """Test Fix model validation."""
        fix = Fix(
            finding_id="test-1",
            file_path=tmp_path / "test.py",
            original_code="vulnerable code",
            fixed_code="secure code",
            explanation="Fixed the vulnerability",
            confidence=0.85,
        )

        assert fix.finding_id == "test-1"
        assert fix.file_path == tmp_path / "test.py"
        assert fix.confidence == 0.85

    def test_fix_model_confidence_validation(self, tmp_path: Path) -> None:
        """Test Fix model confidence bounds."""
        # Valid confidence
        fix = Fix(
            finding_id="test-1",
            file_path=tmp_path / "test.py",
            original_code="code",
            fixed_code="code",
            explanation="explanation",
            confidence=0.5,
        )
        assert fix.confidence == 0.5

        # Test bounds
        with pytest.raises(Exception):  # Pydantic validation error
            Fix(
                finding_id="test-1",
                file_path=tmp_path / "test.py",
                original_code="code",
                fixed_code="code",
                explanation="explanation",
                confidence=1.5,  # Too high
            )
