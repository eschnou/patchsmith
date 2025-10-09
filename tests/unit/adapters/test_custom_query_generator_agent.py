"""Tests for custom query generator agent."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from patchsmith.adapters.claude.agent import AgentError
from patchsmith.adapters.claude.custom_query_generator_agent import (
    CustomQueryGeneratorAgent,
)
from patchsmith.models.finding import Severity


class TestCustomQueryGeneratorAgent:
    """Tests for CustomQueryGeneratorAgent."""

    def test_init(self, tmp_path: Path) -> None:
        """Test agent initialization."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        assert agent.working_dir == tmp_path
        assert agent.agent_name == "CustomQueryGeneratorAgent"

    def test_get_system_prompt(self, tmp_path: Path) -> None:
        """Test system prompt generation."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)
        prompt = agent.get_system_prompt()

        assert "CodeQL" in prompt
        assert "query" in prompt.lower()
        assert "@name" in prompt
        assert "@description" in prompt

    @pytest.mark.asyncio
    @patch.object(CustomQueryGeneratorAgent, "query_claude")
    async def test_execute_success_no_validation(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test successful query generation without validation."""
        # Mock response with valid CodeQL query
        mock_query.return_value = """
/**
 * @name SQL Injection Test
 * @description Detects SQL injection vulnerabilities
 * @kind problem
 * @id custom/python/sql-injection
 * @problem.severity warning
 * @tags security
 */

import python

from CallNode call
where call.getFunction().getName() = "execute"
select call, "Potential SQL injection"
"""

        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        query_id, query_content = await agent.execute(
            language="python",
            project_context="Python web application using Flask",
            vulnerability_type="SQL injection in database queries",
            severity=Severity.HIGH,
            codeql_cli=None,  # No validation
            max_retries=3,
        )

        assert query_id == "custom/python/sql-injection"
        assert "@name SQL Injection Test" in query_content
        assert "import python" in query_content
        assert "select" in query_content
        mock_query.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(CustomQueryGeneratorAgent, "query_claude")
    async def test_execute_with_validation_success(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test query generation with successful compilation validation."""
        mock_query.return_value = """
/**
 * @name Test Query
 * @description Test
 * @kind problem
 * @id custom/test-query
 * @problem.severity warning
 * @tags security
 */

import python

from Expr e
select e
"""

        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        # Mock CodeQL CLI
        mock_codeql = Mock()
        mock_codeql.compile_query.return_value = (True, "")  # Success

        query_id, query_content = await agent.execute(
            language="python",
            project_context="Test context",
            vulnerability_type="Test vulnerability",
            severity=Severity.HIGH,
            codeql_cli=mock_codeql,
            max_retries=3,
        )

        assert query_id == "custom/test-query"
        assert "import python" in query_content
        mock_codeql.compile_query.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(CustomQueryGeneratorAgent, "query_claude")
    async def test_execute_with_validation_retry_success(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test query generation with compilation failure then success."""
        # First response has errors, second is fixed
        first_response = """
/**
 * @name Bad Query
 * @id custom/bad-query
 */
import python
from BadClass x
select x
"""

        second_response = """
/**
 * @name Good Query
 * @id custom/good-query
 */
import python
from Expr e
select e
"""

        mock_query.side_effect = [first_response, second_response]

        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        # Mock CodeQL CLI - first compilation fails, second succeeds
        mock_codeql = Mock()
        mock_codeql.compile_query.side_effect = [
            (False, "Error: BadClass not found"),
            (True, ""),
        ]

        query_id, query_content = await agent.execute(
            language="python",
            project_context="Test context",
            vulnerability_type="Test vulnerability",
            severity=Severity.HIGH,
            codeql_cli=mock_codeql,
            max_retries=3,
        )

        assert query_id == "custom/good-query"
        assert "Good Query" in query_content
        assert mock_query.call_count == 2
        assert mock_codeql.compile_query.call_count == 2

        # Verify second call included error feedback
        second_call_prompt = mock_query.call_args_list[1][1]["prompt"]
        assert "PREVIOUS COMPILATION FAILED" in second_call_prompt
        assert "BadClass not found" in second_call_prompt

    @pytest.mark.asyncio
    @patch.object(CustomQueryGeneratorAgent, "query_claude")
    async def test_execute_max_retries_exceeded(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test failure when max retries exceeded."""
        # Always return invalid query
        mock_query.return_value = """
/**
 * @name Invalid Query
 * @id custom/invalid
 */
import python
from InvalidClass x
select x
"""

        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        # Mock CodeQL CLI - always fails
        mock_codeql = Mock()
        mock_codeql.compile_query.return_value = (False, "Compilation error")

        with pytest.raises(AgentError, match="Query generation failed after"):
            await agent.execute(
                language="python",
                project_context="Test context",
                vulnerability_type="Test vulnerability",
                severity=Severity.HIGH,
                codeql_cli=mock_codeql,
                max_retries=2,
            )

        # Should have tried 3 times (initial + 2 retries)
        assert mock_query.call_count == 3

    def test_parse_response_valid(self, tmp_path: Path) -> None:
        """Test parsing valid query response."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        response = """
/**
 * @name Test Query
 * @description Test description
 * @kind problem
 * @id custom/test
 */

import python

from Expr e
select e, "Test message"
"""

        result = agent._parse_response(response)

        assert "@name Test Query" in result
        assert "import python" in result
        assert "select e" in result

    def test_parse_response_with_markdown_fences(self, tmp_path: Path) -> None:
        """Test parsing response with markdown code fences."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        response = """```ql
/**
 * @name Test Query
 * @id custom/test
 */

import python

select 1
```"""

        result = agent._parse_response(response)

        assert "```" not in result
        assert "@name Test Query" in result
        assert "select 1" in result

    def test_parse_response_missing_metadata(self, tmp_path: Path) -> None:
        """Test parsing fails with missing metadata."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        response = """
import python
select 1
"""

        with pytest.raises(AgentError, match="missing metadata"):
            agent._parse_response(response)

    def test_parse_response_missing_select(self, tmp_path: Path) -> None:
        """Test parsing fails with missing select statement."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        response = """
/**
 * @name Test Query
 */
import python
"""

        with pytest.raises(AgentError, match="missing select"):
            agent._parse_response(response)

    def test_extract_query_id_from_metadata(self, tmp_path: Path) -> None:
        """Test extracting query ID from @id metadata."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        query_content = """
/**
 * @name Test Query
 * @id custom/python/test-query
 */
"""

        query_id = agent._extract_query_id(query_content, "python")

        assert query_id == "custom/python/test-query"

    def test_extract_query_id_from_name_fallback(self, tmp_path: Path) -> None:
        """Test extracting query ID from @name as fallback."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        query_content = """
/**
 * @name SQL Injection Detection
 */
"""

        query_id = agent._extract_query_id(query_content, "python")

        assert "custom/python" in query_id
        assert "sql-injection" in query_id.lower()

    def test_build_generation_prompt(self, tmp_path: Path) -> None:
        """Test building generation prompt."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        prompt = agent._build_generation_prompt(
            language="python",
            project_context="Flask web app with SQLAlchemy",
            vulnerability_type="SQL injection in ORM",
            severity=Severity.HIGH,
            compilation_errors=None,
        )

        assert "python" in prompt
        assert "Flask" in prompt
        assert "SQL injection" in prompt
        assert "high" in prompt.lower()

    def test_build_generation_prompt_with_errors(self, tmp_path: Path) -> None:
        """Test building prompt with compilation errors."""
        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        prompt = agent._build_generation_prompt(
            language="python",
            project_context="Test context",
            vulnerability_type="Test vuln",
            severity=Severity.HIGH,
            compilation_errors="Syntax error at line 10",
        )

        assert "PREVIOUS COMPILATION FAILED" in prompt
        assert "Syntax error at line 10" in prompt
        assert "fix" in prompt.lower()

    @pytest.mark.asyncio
    @patch.object(CustomQueryGeneratorAgent, "query_claude")
    async def test_execute_query_error(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test error handling when query fails."""
        mock_query.side_effect = Exception("API Error")

        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        with pytest.raises(AgentError, match="Custom query generation failed"):
            await agent.execute(
                language="python",
                project_context="Test context",
                vulnerability_type="Test vuln",
                severity=Severity.HIGH,
                codeql_cli=None,
                max_retries=3,
            )

    @pytest.mark.asyncio
    @patch.object(CustomQueryGeneratorAgent, "query_claude")
    async def test_execute_parse_error(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test error handling when parsing fails."""
        mock_query.return_value = "Invalid response without metadata or select"

        agent = CustomQueryGeneratorAgent(working_dir=tmp_path)

        with pytest.raises(AgentError, match="Custom query generation failed"):
            await agent.execute(
                language="python",
                project_context="Test context",
                vulnerability_type="Test vuln",
                severity=Severity.HIGH,
                codeql_cli=None,
                max_retries=3,
            )
