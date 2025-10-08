"""Tests for language detection agent."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from patchsmith.adapters.claude.language_detection_agent import LanguageDetectionAgent
from patchsmith.adapters.claude.agent import AgentError
from patchsmith.models.project import LanguageDetection


class TestLanguageDetectionAgent:
    """Tests for LanguageDetectionAgent."""

    def test_init(self, tmp_path: Path) -> None:
        """Test agent initialization."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)

        assert agent.working_dir == tmp_path
        assert agent.agent_name == "LanguageDetectionAgent"

    def test_get_system_prompt(self, tmp_path: Path) -> None:
        """Test system prompt generation."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        prompt = agent.get_system_prompt()

        assert "programming language detection" in prompt.lower()
        assert "submit_languages" in prompt  # Tool-based approach
        assert "confidence" in prompt.lower()

    def test_build_analysis_prompt(self, tmp_path: Path) -> None:
        """Test analysis prompt building."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        prompt = agent._build_analysis_prompt(tmp_path, max_files=50)

        # User prompt should contain task-specific info
        assert str(tmp_path) in prompt
        assert "50" in prompt
        assert "Glob" in prompt  # Tool instructions

        # Tool-based instructions should be in system prompt
        system_prompt = agent.get_system_prompt()
        assert "submit_languages" in system_prompt

    @pytest.mark.asyncio
    @patch.object(LanguageDetectionAgent, "query_claude")
    async def test_execute_success(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test successful language detection."""
        # Mock Claude response
        mock_query.return_value = """
Based on my analysis, I found:
[
  {"name": "python", "confidence": 0.95, "evidence": ["Found .py files"]},
  {"name": "javascript", "confidence": 0.80, "evidence": ["Found .js files"]}
]
"""

        agent = LanguageDetectionAgent(working_dir=tmp_path)
        languages = await agent.execute()

        assert len(languages) == 2
        assert languages[0].name == "python"
        assert languages[0].confidence == 0.95
        assert languages[1].name == "javascript"
        assert languages[1].confidence == 0.80

        # Verify query_claude was called correctly
        mock_query.assert_called_once()
        call_args = mock_query.call_args
        assert "prompt" in call_args.kwargs
        assert "max_turns" in call_args.kwargs
        assert "allowed_tools" in call_args.kwargs

    @pytest.mark.asyncio
    @patch.object(LanguageDetectionAgent, "query_claude")
    async def test_execute_with_custom_path(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test language detection with custom project path."""
        custom_path = tmp_path / "project"
        custom_path.mkdir()

        mock_query.return_value = '[{"name": "python", "confidence": 0.90}]'

        agent = LanguageDetectionAgent(working_dir=tmp_path)
        languages = await agent.execute(project_path=custom_path)

        assert len(languages) == 1
        assert languages[0].name == "python"

    @pytest.mark.asyncio
    async def test_execute_path_not_exists(self, tmp_path: Path) -> None:
        """Test error when project path doesn't exist."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(AgentError, match="does not exist"):
            await agent.execute(project_path=nonexistent)

    @pytest.mark.asyncio
    async def test_execute_path_not_directory(self, tmp_path: Path) -> None:
        """Test error when project path is not a directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        agent = LanguageDetectionAgent(working_dir=tmp_path)

        with pytest.raises(AgentError, match="not a directory"):
            await agent.execute(project_path=file_path)

    def test_parse_response_success(self, tmp_path: Path) -> None:
        """Test successful response parsing."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = """
Here are the detected languages:
[
  {"name": "python", "confidence": 0.95, "evidence": ["Found .py files"]},
  {"name": "go", "confidence": 0.85, "evidence": ["Found .go files", "go.mod present"]}
]
"""

        languages = agent._parse_response(response)

        assert len(languages) == 2
        assert languages[0].name == "python"
        assert languages[0].confidence == 0.95
        assert languages[0].evidence == ["Found .py files"]
        assert languages[1].name == "go"
        assert languages[1].confidence == 0.85
        assert len(languages[1].evidence) == 2

    def test_parse_response_no_json(self, tmp_path: Path) -> None:
        """Test parsing error when no JSON found."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = "No JSON array here"

        with pytest.raises(AgentError, match="No JSON array found"):
            agent._parse_response(response)

    def test_parse_response_invalid_json(self, tmp_path: Path) -> None:
        """Test parsing error with invalid JSON."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = "[{invalid json}]"

        with pytest.raises(AgentError, match="Failed to parse JSON"):
            agent._parse_response(response)

    def test_parse_response_not_array(self, tmp_path: Path) -> None:
        """Test parsing error when JSON is not an array."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = '{"name": "python"}'

        with pytest.raises(AgentError, match="Failed to parse response"):
            agent._parse_response(response)

    def test_parse_response_missing_fields(self, tmp_path: Path) -> None:
        """Test parsing with missing required fields (should skip item)."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = """
[
  {"name": "python", "confidence": 0.95},
  {"name": "javascript"},
  {"confidence": 0.80}
]
"""

        languages = agent._parse_response(response)

        # Only first item has both required fields
        assert len(languages) == 1
        assert languages[0].name == "python"

    def test_parse_response_non_dict_items(self, tmp_path: Path) -> None:
        """Test parsing with non-dictionary items (should skip)."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = """
[
  {"name": "python", "confidence": 0.95},
  "not a dict",
  42,
  {"name": "go", "confidence": 0.80}
]
"""

        languages = agent._parse_response(response)

        # Only dict items with required fields
        assert len(languages) == 2
        assert languages[0].name == "python"
        assert languages[1].name == "go"

    def test_parse_response_empty_array(self, tmp_path: Path) -> None:
        """Test parsing empty JSON array."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = "[]"

        languages = agent._parse_response(response)

        assert len(languages) == 0

    def test_parse_response_confidence_conversion(self, tmp_path: Path) -> None:
        """Test confidence is converted to float."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = '[{"name": "python", "confidence": "0.95"}]'

        languages = agent._parse_response(response)

        assert len(languages) == 1
        assert isinstance(languages[0].confidence, float)
        assert languages[0].confidence == 0.95

    @pytest.mark.asyncio
    @patch.object(LanguageDetectionAgent, "query_claude")
    async def test_execute_query_error(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test error handling when query fails."""
        mock_query.side_effect = Exception("API Error")

        agent = LanguageDetectionAgent(working_dir=tmp_path)

        with pytest.raises(AgentError, match="Language detection failed"):
            await agent.execute()

    @pytest.mark.asyncio
    @patch.object(LanguageDetectionAgent, "query_claude")
    async def test_execute_parse_error(
        self, mock_query: AsyncMock, tmp_path: Path
    ) -> None:
        """Test error handling when parsing fails."""
        mock_query.return_value = "Invalid response format"

        agent = LanguageDetectionAgent(working_dir=tmp_path)

        with pytest.raises(AgentError, match="Language detection failed"):
            await agent.execute()

    def test_parse_response_with_evidence_array(self, tmp_path: Path) -> None:
        """Test parsing response with evidence as array."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = """
[
  {
    "name": "python",
    "confidence": 0.95,
    "evidence": ["Found .py files", "requirements.txt present"]
  }
]
"""

        languages = agent._parse_response(response)

        assert len(languages) == 1
        assert languages[0].name == "python"
        assert languages[0].confidence == 0.95
        assert len(languages[0].evidence) == 2
        assert "Found .py files" in languages[0].evidence

    def test_parse_response_evidence_string_converted(self, tmp_path: Path) -> None:
        """Test that evidence string is converted to array."""
        agent = LanguageDetectionAgent(working_dir=tmp_path)
        response = '[{"name": "python", "confidence": 0.95, "evidence": "Found .py files"}]'

        languages = agent._parse_response(response)

        assert len(languages) == 1
        assert languages[0].evidence == ["Found .py files"]
