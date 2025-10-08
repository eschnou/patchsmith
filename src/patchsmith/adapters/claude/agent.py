"""Base agent class for Claude AI agents."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from patchsmith.utils.logging import get_logger

logger = get_logger()


class AgentError(Exception):
    """Agent operation failed."""

    pass


class BaseAgent(ABC):
    """Base class for Claude AI agents.

    Provides common functionality for interacting with Claude Code via the Agent SDK.
    Subclasses should implement the execute() method to define specific agent behavior.
    """

    def __init__(
        self,
        working_dir: Path | None = None,
        max_turns: int = 100,
        allowed_tools: list[str] | None = None,
        thinking_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """
        Initialize base agent.

        Args:
            working_dir: Working directory for agent operations
            max_turns: Maximum conversation turns with Claude
            allowed_tools: List of allowed tools (None = all tools)
            thinking_callback: Optional callback to receive agent thinking updates
            progress_callback: Optional callback for turn progress (current_turn, max_turns)
        """
        self.working_dir = working_dir or Path.cwd()
        self.max_turns = max_turns
        self.allowed_tools = allowed_tools
        self.thinking_callback = thinking_callback
        self.progress_callback = progress_callback
        self.agent_name = self.__class__.__name__

        logger.info(
            "agent_initialized",
            agent=self.agent_name,
            working_dir=str(self.working_dir),
            max_turns=self.max_turns,
        )

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """
        Execute the agent's primary task.

        This method must be implemented by subclasses to define the agent's behavior.

        Args:
            **kwargs: Agent-specific parameters

        Returns:
            Agent-specific result

        Raises:
            AgentError: If execution fails
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent.

        This method must be implemented by subclasses to define the agent's role
        and instructions.

        Returns:
            System prompt text
        """
        pass

    async def query_claude(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_turns: int | None = None,
        allowed_tools: list[str] | None = None,
        custom_tools: list[dict] | None = None,
    ) -> str:
        """
        Query Claude Code with a prompt.

        Args:
            prompt: The prompt to send to Claude
            system_prompt: Optional system prompt (uses get_system_prompt() if None)
            max_turns: Optional max turns override
            allowed_tools: Optional allowed tools override

        Returns:
            Claude's complete response as text

        Raises:
            AgentError: If query fails
        """
        logger.info(
            "agent_query_started",
            agent=self.agent_name,
            prompt_length=len(prompt),
        )

        try:
            # Prepare options
            tools = allowed_tools or self.allowed_tools
            options = ClaudeAgentOptions(
                system_prompt=system_prompt or self.get_system_prompt(),
                max_turns=max_turns or self.max_turns,
                allowed_tools=tools if tools is not None else [],
                cwd=str(self.working_dir),
            )

            # Query Claude and collect response
            response_parts: list[str] = []

            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)

                async for message in client.receive_response():
                    # Debug: log raw message format
                    logger.debug(
                        "agent_received_message",
                        agent=self.agent_name,
                        message_type=type(message).__name__,
                        has_content=hasattr(message, "content"),
                        has_text=hasattr(message, "text"),
                    )

                    # Extract text content from message objects or dicts
                    # Messages can be objects with attributes or dicts
                    if hasattr(message, "content"):
                        # Message object with content attribute
                        content = message.content
                        if isinstance(content, str):
                            response_parts.append(content)
                        elif isinstance(content, list):
                            for item in content:
                                if hasattr(item, "text"):
                                    response_parts.append(item.text)
                                elif isinstance(item, dict) and item.get("type") == "text":
                                    response_parts.append(item.get("text", ""))
                    elif hasattr(message, "text"):
                        # Message object with text attribute
                        response_parts.append(message.text)
                    elif isinstance(message, dict):
                        # Dictionary message format
                        if "content" in message:
                            content = message["content"]
                            if isinstance(content, str):
                                response_parts.append(content)
                            elif isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and item.get("type") == "text":
                                        response_parts.append(item.get("text", ""))
                        elif "text" in message:
                            response_parts.append(message["text"])
                    elif isinstance(message, str):
                        response_parts.append(message)

            response = "\n".join(response_parts).strip()

            logger.info(
                "agent_query_completed",
                agent=self.agent_name,
                response_length=len(response),
            )

            return response

        except Exception as e:
            logger.error(
                "agent_query_failed",
                agent=self.agent_name,
                error=str(e),
            )
            raise AgentError(f"Failed to query Claude: {e}") from e

    def validate_working_dir(self) -> None:
        """
        Validate that working directory exists and is accessible.

        Raises:
            AgentError: If working directory is invalid
        """
        if not self.working_dir.exists():
            raise AgentError(f"Working directory does not exist: {self.working_dir}")

        if not self.working_dir.is_dir():
            raise AgentError(f"Working directory is not a directory: {self.working_dir}")

        logger.debug(
            "agent_working_dir_validated",
            agent=self.agent_name,
            working_dir=str(self.working_dir),
        )

    def _emit_thinking(self, message: str) -> None:
        """
        Emit agent thinking status to callback if set.

        Args:
            message: Thinking status message
        """
        if self.thinking_callback:
            # Truncate long messages to keep UI clean
            truncated = message[:80] + "..." if len(message) > 80 else message
            self.thinking_callback(truncated)

    def _emit_progress(self, current_turn: int) -> None:
        """
        Emit agent progress (turn count) to callback if set.

        Args:
            current_turn: Current turn number
        """
        if self.progress_callback:
            self.progress_callback(current_turn, self.max_turns)

    def _extract_thinking_from_message(self, message: Any) -> str | None:
        """
        Extract thinking/status from an agent message.

        Parses AssistantMessage for text blocks (agent reasoning) and tool use
        to create user-friendly status messages.

        Args:
            message: Message from agent stream

        Returns:
            Thinking status string, or None if no thinking found
        """
        message_type = type(message).__name__

        # Extract from AssistantMessage
        if message_type == "AssistantMessage" and hasattr(message, "content"):
            content = message.content

            # Debug: log content structure
            logger.debug(
                "extracting_thinking",
                agent=self.agent_name,
                content_type=type(content).__name__,
                is_list=isinstance(content, list),
                content_length=len(content) if isinstance(content, list) else None,
            )

            if isinstance(content, list):
                for idx, item in enumerate(content):
                    item_type = type(item).__name__

                    # Debug: log each item
                    logger.debug(
                        "extracting_thinking_item",
                        agent=self.agent_name,
                        item_index=idx,
                        item_type=item_type,
                        has_type_attr=hasattr(item, "type"),
                        has_text_attr=hasattr(item, "text"),
                        has_name_attr=hasattr(item, "name"),
                    )

                    # Extract agent reasoning text from TextBlock
                    if item_type == "TextBlock" and hasattr(item, "text"):
                        text = item.text.strip()
                        if text:
                            # Return first non-empty text block
                            return text

                    # Extract tool use from ToolUseBlock
                    elif item_type == "ToolUseBlock" and hasattr(item, "name"):
                        tool_name = item.name
                        tool_input = getattr(item, "input", {})

                        # Create friendly messages for common tools
                        if tool_name == "Read" or "read" in tool_name.lower():
                            file_path = tool_input.get("file_path", "file")
                            return f"Reading {file_path}..."
                        elif tool_name == "Write" or "write" in tool_name.lower():
                            file_path = tool_input.get("file_path", "file")
                            return f"Writing to {file_path}..."
                        elif tool_name == "Glob" or "glob" in tool_name.lower():
                            pattern = tool_input.get("pattern", "*")
                            return f"Searching for {pattern}..."
                        elif "submit" in tool_name.lower() or "complete" in tool_name.lower():
                            return "Finalizing results..."
                        else:
                            return f"Using {tool_name}..."

                    # Fallback: check for .type attribute (alternative SDK format)
                    elif hasattr(item, "type"):
                        if item.type == "text" and hasattr(item, "text"):
                            text = item.text.strip()
                            if text:
                                return text
                        elif item.type == "tool_use" and hasattr(item, "name"):
                            tool_name = item.name
                            tool_input = getattr(item, "input", {})
                            if "read" in tool_name.lower():
                                file_path = tool_input.get("file_path", "file")
                                return f"Reading {file_path}..."
                            elif "glob" in tool_name.lower():
                                pattern = tool_input.get("pattern", "*")
                                return f"Searching for {pattern}..."
                            else:
                                return f"Using {tool_name}..."

        return None
