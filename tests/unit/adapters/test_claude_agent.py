"""Tests for Claude base agent."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from patchsmith.adapters.claude.agent import AgentError, BaseAgent


class TestAgent(BaseAgent):
    """Test agent implementation."""

    async def execute(self, **kwargs):  # type: ignore
        """Test execution."""
        return "test_result"

    def get_system_prompt(self) -> str:
        """Test system prompt."""
        return "You are a test agent."


class TestBaseAgent:
    """Tests for BaseAgent base class."""

    def test_init_default(self, tmp_path: Path) -> None:
        """Test agent initialization with defaults."""
        agent = TestAgent(working_dir=tmp_path)

        assert agent.working_dir == tmp_path
        assert agent.max_turns == 10
        assert agent.allowed_tools is None
        assert agent.agent_name == "TestAgent"

    def test_init_custom(self, tmp_path: Path) -> None:
        """Test agent initialization with custom values."""
        agent = TestAgent(
            working_dir=tmp_path,
            max_turns=5,
            allowed_tools=["Read", "Write"],
        )

        assert agent.working_dir == tmp_path
        assert agent.max_turns == 5
        assert agent.allowed_tools == ["Read", "Write"]

    def test_init_no_working_dir(self) -> None:
        """Test agent initialization without working directory."""
        agent = TestAgent()

        # Should default to current directory
        assert agent.working_dir == Path.cwd()

    @pytest.mark.asyncio
    async def test_execute_abstract(self) -> None:
        """Test that execute is implemented in subclass."""
        agent = TestAgent()
        result = await agent.execute(test="value")

        assert result == "test_result"

    def test_get_system_prompt_abstract(self) -> None:
        """Test that get_system_prompt is implemented in subclass."""
        agent = TestAgent()
        prompt = agent.get_system_prompt()

        assert prompt == "You are a test agent."

    @pytest.mark.asyncio
    @patch("patchsmith.adapters.claude.agent.ClaudeSDKClient")
    async def test_query_claude_success(
        self, mock_client_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test successful Claude query."""
        # Setup mock client
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.query = AsyncMock()

        # Mock message objects with content attribute (like real SDK)
        class MockContent:
            def __init__(self, text):
                self.text = text

        class MockMessage:
            def __init__(self, content_items):
                self.content = content_items

        # Mock response messages
        async def mock_receive():
            yield MockMessage([MockContent("Hello")])
            yield MockMessage([MockContent("World")])

        mock_client.receive_response = mock_receive
        mock_client_class.return_value = mock_client

        agent = TestAgent(working_dir=tmp_path)
        response = await agent.query_claude("Test prompt")

        assert response == "Hello\nWorld"
        mock_client.query.assert_called_once_with("Test prompt")

    @pytest.mark.asyncio
    @patch("patchsmith.adapters.claude.agent.ClaudeSDKClient")
    async def test_query_claude_with_options(
        self, mock_client_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test Claude query with custom options."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield {"text": "Response"}

        mock_client.receive_response = mock_receive
        mock_client_class.return_value = mock_client

        agent = TestAgent(working_dir=tmp_path)
        response = await agent.query_claude(
            "Test prompt",
            system_prompt="Custom system prompt",
            max_turns=3,
            allowed_tools=["Read"],
        )

        assert response == "Response"

    @pytest.mark.asyncio
    @patch("patchsmith.adapters.claude.agent.ClaudeSDKClient")
    async def test_query_claude_string_response(
        self, mock_client_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test Claude query with string response."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield "Simple string response"

        mock_client.receive_response = mock_receive
        mock_client_class.return_value = mock_client

        agent = TestAgent(working_dir=tmp_path)
        response = await agent.query_claude("Test")

        assert response == "Simple string response"

    @pytest.mark.asyncio
    @patch("patchsmith.adapters.claude.agent.ClaudeSDKClient")
    async def test_query_claude_dict_with_content_string(
        self, mock_client_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test Claude query with dict containing content string."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.query = AsyncMock()

        async def mock_receive():
            yield {"content": "Direct content string"}

        mock_client.receive_response = mock_receive
        mock_client_class.return_value = mock_client

        agent = TestAgent(working_dir=tmp_path)
        response = await agent.query_claude("Test")

        assert response == "Direct content string"

    @pytest.mark.asyncio
    @patch("patchsmith.adapters.claude.agent.ClaudeSDKClient")
    async def test_query_claude_failure(
        self, mock_client_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test Claude query failure."""
        mock_client = AsyncMock()
        # Make __aenter__ raise the error instead of query
        mock_client.__aenter__ = AsyncMock(side_effect=Exception("API Error"))
        mock_client.__aexit__ = AsyncMock()
        mock_client_class.return_value = mock_client

        agent = TestAgent(working_dir=tmp_path)

        with pytest.raises(AgentError, match="Failed to query Claude"):
            await agent.query_claude("Test prompt")

    def test_validate_working_dir_success(self, tmp_path: Path) -> None:
        """Test working directory validation success."""
        agent = TestAgent(working_dir=tmp_path)
        agent.validate_working_dir()  # Should not raise

    def test_validate_working_dir_not_exists(self, tmp_path: Path) -> None:
        """Test working directory validation when directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"
        agent = TestAgent(working_dir=nonexistent)

        with pytest.raises(AgentError, match="does not exist"):
            agent.validate_working_dir()

    def test_validate_working_dir_not_directory(self, tmp_path: Path) -> None:
        """Test working directory validation when path is not a directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        agent = TestAgent(working_dir=file_path)

        with pytest.raises(AgentError, match="not a directory"):
            agent.validate_working_dir()

    def test_cannot_instantiate_base_agent_directly(self) -> None:
        """Test that BaseAgent cannot be instantiated without implementing abstract methods."""
        # This test verifies the ABC pattern works correctly
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore
