"""Tests for query generator agent."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from patchsmith.adapters.claude.agent import AgentError
from patchsmith.adapters.claude.query_generator_agent import QueryGeneratorAgent
from patchsmith.models.finding import Severity
from patchsmith.models.query import Query, QuerySuite


class TestQueryGeneratorAgent:
    """Tests for QueryGeneratorAgent."""

    def test_init(self, tmp_path: Path) -> None:
        """Test agent initialization."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)

        assert agent.working_dir == tmp_path
        assert agent.agent_name == "QueryGeneratorAgent"

    def test_get_system_prompt(self, tmp_path: Path) -> None:
        """Test system prompt generation."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        prompt = agent.get_system_prompt()

        assert "CodeQL query expert" in prompt
        assert "JSON" in prompt
        assert "severity" in prompt.lower()

    def test_build_generation_prompt(self, tmp_path: Path) -> None:
        """Test generation prompt building."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        prompt = agent._build_generation_prompt(
            languages=["python", "javascript"],
            focus_areas=["SQL injection", "XSS"],
            min_severity=Severity.HIGH,
        )

        assert "python" in prompt
        assert "javascript" in prompt
        assert "SQL injection" in prompt
        assert "XSS" in prompt
        assert "high" in prompt.lower()

    def test_build_generation_prompt_no_focus(self, tmp_path: Path) -> None:
        """Test generation prompt without focus areas."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        prompt = agent._build_generation_prompt(
            languages=["python"],
            focus_areas=None,
            min_severity=Severity.MEDIUM,
        )

        assert "python" in prompt
        assert "medium" in prompt.lower()

    @pytest.mark.asyncio
    @patch.object(QueryGeneratorAgent, "query_claude")
    async def test_execute_success(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test successful query generation."""
        mock_query.return_value = """
{
  "queries": [
    {
      "id": "python/sql-injection",
      "name": "SQL Injection",
      "description": "Detects SQL injection",
      "path": "codeql/python-queries:Security/CWE-089/SqlInjection.ql",
      "severity": "high",
      "language": "python",
      "tags": ["security", "cwe-89"],
      "is_custom": false
    }
  ],
  "suite_recommendations": ["codeql/python-queries:codeql-suites/python-security.qls"]
}
"""

        agent = QueryGeneratorAgent(working_dir=tmp_path)
        suite = await agent.execute(languages=["python"])

        assert len(suite.queries) == 1
        assert suite.queries[0].id == "python/sql-injection"
        assert suite.queries[0].name == "SQL Injection"
        assert suite.queries[0].severity == Severity.HIGH
        assert suite.queries[0].language == "python"
        assert "cwe-89" in suite.queries[0].tags

    @pytest.mark.asyncio
    @patch.object(QueryGeneratorAgent, "query_claude")
    async def test_execute_multiple_queries(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test generation with multiple queries."""
        mock_query.return_value = """
{
  "queries": [
    {
      "id": "python/sql-injection",
      "name": "SQL Injection",
      "path": "codeql/python-queries:Security/CWE-089/SqlInjection.ql",
      "severity": "high",
      "language": "python"
    },
    {
      "id": "python/xss",
      "name": "Cross-site Scripting",
      "path": "codeql/python-queries:Security/CWE-079/XSS.ql",
      "severity": "high",
      "language": "python"
    }
  ]
}
"""

        agent = QueryGeneratorAgent(working_dir=tmp_path)
        suite = await agent.execute(languages=["python"])

        assert len(suite.queries) == 2
        assert suite.queries[0].id == "python/sql-injection"
        assert suite.queries[1].id == "python/xss"

    @pytest.mark.asyncio
    @patch.object(QueryGeneratorAgent, "query_claude")
    async def test_execute_with_focus_areas(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test generation with focus areas."""
        mock_query.return_value = """
{
  "queries": [
    {
      "id": "python/sql-injection",
      "name": "SQL Injection",
      "path": "codeql/python-queries:Security/CWE-089/SqlInjection.ql",
      "severity": "critical",
      "language": "python"
    }
  ]
}
"""

        agent = QueryGeneratorAgent(working_dir=tmp_path)
        suite = await agent.execute(
            languages=["python"],
            focus_areas=["SQL injection"],
            min_severity=Severity.HIGH,
        )

        assert len(suite.queries) == 1
        assert suite.queries[0].severity == Severity.CRITICAL

        # Verify query_claude was called with correct parameters
        mock_query.assert_called_once()
        call_args = mock_query.call_args
        assert "SQL injection" in call_args.kwargs["prompt"]

    def test_parse_response_success(self, tmp_path: Path) -> None:
        """Test successful response parsing."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        response = """
{
  "queries": [
    {
      "id": "python/sql-injection",
      "name": "SQL Injection",
      "description": "Detects SQL injection vulnerabilities",
      "path": "codeql/python-queries:Security/CWE-089/SqlInjection.ql",
      "severity": "high",
      "language": "python",
      "tags": ["security", "cwe-89", "injection"],
      "is_custom": false
    }
  ]
}
"""

        suite = agent._parse_response(response, ["python"])

        assert len(suite.queries) == 1
        query = suite.queries[0]
        assert query.id == "python/sql-injection"
        assert query.name == "SQL Injection"
        assert query.description == "Detects SQL injection vulnerabilities"
        assert query.severity == Severity.HIGH
        assert query.language == "python"
        assert len(query.tags) == 3
        assert not query.is_custom

    def test_parse_response_no_json(self, tmp_path: Path) -> None:
        """Test parsing error when no JSON found."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        response = "No JSON here"

        with pytest.raises(AgentError, match="No JSON object found"):
            agent._parse_response(response, ["python"])

    def test_parse_response_invalid_json(self, tmp_path: Path) -> None:
        """Test parsing error with invalid JSON."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        response = "{invalid json}"

        with pytest.raises(AgentError, match="Failed to parse JSON"):
            agent._parse_response(response, ["python"])

    def test_parse_response_not_object(self, tmp_path: Path) -> None:
        """Test parsing error when JSON is not an object."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        response = '["array", "not", "object"]'

        with pytest.raises(AgentError, match="Failed to parse response"):
            agent._parse_response(response, ["python"])

    def test_parse_response_missing_required_fields(self, tmp_path: Path) -> None:
        """Test parsing with missing required fields (should skip)."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        response = """
{
  "queries": [
    {
      "id": "python/valid",
      "name": "Valid Query",
      "path": "path/to/query.ql",
      "language": "python"
    },
    {
      "id": "python/missing-name",
      "path": "path/to/query.ql",
      "language": "python"
    },
    {
      "name": "Missing ID",
      "path": "path/to/query.ql",
      "language": "python"
    }
  ]
}
"""

        suite = agent._parse_response(response, ["python"])

        # Only first query has all required fields
        assert len(suite.queries) == 1
        assert suite.queries[0].id == "python/valid"

    def test_parse_response_non_dict_items(self, tmp_path: Path) -> None:
        """Test parsing with non-dictionary items (should skip)."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        response = """
{
  "queries": [
    {
      "id": "python/valid",
      "name": "Valid Query",
      "path": "path/to/query.ql",
      "language": "python"
    },
    "not a dict",
    42
  ]
}
"""

        suite = agent._parse_response(response, ["python"])

        assert len(suite.queries) == 1
        assert suite.queries[0].id == "python/valid"

    def test_parse_response_empty_queries(self, tmp_path: Path) -> None:
        """Test parsing with empty queries array."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        response = '{"queries": []}'

        suite = agent._parse_response(response, ["python"])

        assert len(suite.queries) == 0

    def test_parse_severity(self, tmp_path: Path) -> None:
        """Test severity parsing."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)

        assert agent._parse_severity("critical") == Severity.CRITICAL
        assert agent._parse_severity("high") == Severity.HIGH
        assert agent._parse_severity("medium") == Severity.MEDIUM
        assert agent._parse_severity("low") == Severity.LOW
        assert agent._parse_severity("info") == Severity.INFO

        # Test case insensitive
        assert agent._parse_severity("HIGH") == Severity.HIGH
        assert agent._parse_severity("Critical") == Severity.CRITICAL

        # Test unknown defaults to MEDIUM
        assert agent._parse_severity("unknown") == Severity.MEDIUM

    def test_parse_response_default_values(self, tmp_path: Path) -> None:
        """Test parsing with default values for optional fields."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        response = """
{
  "queries": [
    {
      "id": "python/simple",
      "name": "Simple Query",
      "path": "path/to/query.ql",
      "language": "python"
    }
  ]
}
"""

        suite = agent._parse_response(response, ["python"])

        assert len(suite.queries) == 1
        query = suite.queries[0]
        assert query.description is None
        assert query.severity == Severity.MEDIUM  # Default
        assert query.tags == []
        assert not query.is_custom

    @pytest.mark.asyncio
    @patch.object(QueryGeneratorAgent, "query_claude")
    async def test_execute_query_error(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test error handling when query fails."""
        mock_query.side_effect = Exception("API Error")

        agent = QueryGeneratorAgent(working_dir=tmp_path)

        with pytest.raises(AgentError, match="Query generation failed"):
            await agent.execute(languages=["python"])

    @pytest.mark.asyncio
    @patch.object(QueryGeneratorAgent, "query_claude")
    async def test_execute_parse_error(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test error handling when parsing fails."""
        mock_query.return_value = "Invalid response format"

        agent = QueryGeneratorAgent(working_dir=tmp_path)

        with pytest.raises(AgentError, match="Query generation failed"):
            await agent.execute(languages=["python"])

    def test_parse_response_multiple_languages(self, tmp_path: Path) -> None:
        """Test suite name with multiple languages."""
        agent = QueryGeneratorAgent(working_dir=tmp_path)
        response = '{"queries": []}'

        suite = agent._parse_response(response, ["python", "javascript", "java"])

        assert "python/javascript/java" in suite.name
        assert "python/javascript/java" in suite.description

    def test_validate_queries_valid_standard_query(self, tmp_path: Path) -> None:
        """Test validation passes for valid standard queries."""
        from patchsmith.adapters.codeql.cli import CodeQLCLI

        agent = QueryGeneratorAgent(working_dir=tmp_path)
        query = Query(
            id="python/sql-injection",
            name="SQL Injection",
            path=Path("codeql/python-queries:Security/CWE-089/SqlInjection.ql"),
            severity=Severity.HIGH,
            language="python",
        )
        suite = QuerySuite(
            name="Test Suite",
            description="Test",
            queries=[query],
        )

        errors = agent._validate_queries(suite, CodeQLCLI())

        assert errors is None

    def test_validate_queries_invalid_pack_format(self, tmp_path: Path) -> None:
        """Test validation fails for invalid pack format."""
        from patchsmith.adapters.codeql.cli import CodeQLCLI

        agent = QueryGeneratorAgent(working_dir=tmp_path)
        query = Query(
            id="python/bad-query",
            name="Bad Query",
            path=Path("bad-format:path/to/query.ql"),  # Missing org/ prefix
            severity=Severity.HIGH,
            language="python",
        )
        suite = QuerySuite(
            name="Test Suite",
            description="Test",
            queries=[query],
        )

        errors = agent._validate_queries(suite, CodeQLCLI())

        assert errors is not None
        assert "Invalid pack format" in errors
        assert "python/bad-query" in errors

    def test_validate_queries_custom_file_not_exists(self, tmp_path: Path) -> None:
        """Test validation fails when custom query file doesn't exist."""
        from patchsmith.adapters.codeql.cli import CodeQLCLI

        agent = QueryGeneratorAgent(working_dir=tmp_path)
        query = Query(
            id="custom/missing",
            name="Missing Query",
            path=tmp_path / "nonexistent.ql",
            severity=Severity.HIGH,
            language="python",
        )
        suite = QuerySuite(
            name="Test Suite",
            description="Test",
            queries=[query],
        )

        errors = agent._validate_queries(suite, CodeQLCLI())

        assert errors is not None
        assert "File not found" in errors
        assert "custom/missing" in errors

    def test_validate_queries_invalid_path(self, tmp_path: Path) -> None:
        """Test validation fails for invalid query path."""
        from patchsmith.adapters.codeql.cli import CodeQLCLI

        agent = QueryGeneratorAgent(working_dir=tmp_path)
        query = Query(
            id="invalid/path",
            name="Invalid Path",
            path=Path("some/random/path.txt"),  # Not .ql, no :
            severity=Severity.HIGH,
            language="python",
        )
        suite = QuerySuite(
            name="Test Suite",
            description="Test",
            queries=[query],
        )

        errors = agent._validate_queries(suite, CodeQLCLI())

        assert errors is not None
        assert "Invalid query path" in errors
        assert "invalid/path" in errors

    @pytest.mark.asyncio
    @patch.object(QueryGeneratorAgent, "query_claude")
    async def test_execute_with_validation_disabled(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test execution with validation disabled."""
        mock_query.return_value = """
{
  "queries": [
    {
      "id": "python/test",
      "name": "Test Query",
      "path": "invalid-format",
      "severity": "high",
      "language": "python"
    }
  ]
}
"""

        agent = QueryGeneratorAgent(working_dir=tmp_path)
        suite = await agent.execute(languages=["python"], validate_queries=False)

        assert len(suite.queries) == 1
        mock_query.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(QueryGeneratorAgent, "query_claude")
    async def test_execute_with_validation_retry(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test retry logic when validation fails."""
        # First response has invalid query
        first_response = """
{
  "queries": [
    {
      "id": "python/bad",
      "name": "Bad Query",
      "path": "bad:query.ql",
      "severity": "high",
      "language": "python"
    }
  ]
}
"""
        # Second response has valid query
        second_response = """
{
  "queries": [
    {
      "id": "python/good",
      "name": "Good Query",
      "path": "codeql/python-queries:Security/test.ql",
      "severity": "high",
      "language": "python"
    }
  ]
}
"""

        mock_query.side_effect = [first_response, second_response]

        agent = QueryGeneratorAgent(working_dir=tmp_path)
        suite = await agent.execute(languages=["python"], validate_queries=True, max_retries=2)

        assert len(suite.queries) == 1
        assert suite.queries[0].id == "python/good"
        assert mock_query.call_count == 2

        # Check that second call included validation errors
        second_call = mock_query.call_args_list[1]
        assert "PREVIOUS ATTEMPT HAD ERRORS" in second_call.kwargs["prompt"]

    @pytest.mark.asyncio
    @patch.object(QueryGeneratorAgent, "query_claude")
    async def test_execute_validation_max_retries_exceeded(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test error when max retries exceeded."""
        # Always return invalid queries
        mock_query.return_value = """
{
  "queries": [
    {
      "id": "python/bad",
      "name": "Bad Query",
      "path": "bad:query.ql",
      "severity": "high",
      "language": "python"
    }
  ]
}
"""

        agent = QueryGeneratorAgent(working_dir=tmp_path)

        with pytest.raises(AgentError, match="Query generation failed after"):
            await agent.execute(languages=["python"], validate_queries=True, max_retries=1)
