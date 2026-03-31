"""Tests for the Agent core functionality."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agent import Agent, ToolDef, _registry, execute_tool, registered_tools, tool_names


class TestToolRegistry:
    """Test the tool registration system."""

    def test_tool_decorator_registers_function(self) -> None:
        """Test that @tool decorator registers the function."""
        # The registry should contain tools after import
        assert len(_registry) > 0

    def test_registered_tools_returns_list(self) -> None:
        """Test that registered_tools returns a list of tool schemas."""
        tools = registered_tools()
        assert isinstance(tools, list)
        if tools:
            assert "function" in tools[0]

    def test_tool_names_returns_list(self) -> None:
        """Test that tool_names returns a list of strings."""
        names = tool_names()
        assert isinstance(names, list)
        assert all(isinstance(name, str) for name in names)


class TestToolDef:
    """Test ToolDef dataclass."""

    def test_openai_schema_format(self) -> None:
        """Test that openai_schema returns correct format."""

        def dummy_fn(x: str) -> str:
            return x

        tool_def = ToolDef(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {"x": {"type": "string"}},
            },
            fn=dummy_fn,
        )
        schema = tool_def.openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        assert schema["function"]["description"] == "A test tool"


class TestExecuteTool:
    """Test execute_tool function."""

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self) -> None:
        """Test executing a non-existent tool."""
        result = await execute_tool("nonexistent_tool", {})
        assert "unknown tool" in result

    @pytest.mark.asyncio
    async def test_execute_registered_tool(self) -> None:
        """Test executing a registered tool."""
        # Get a registered tool name
        if _registry:
            tool_name = next(iter(_registry.keys()))
            # Should not return "unknown tool" error
            result = await execute_tool(tool_name, {})
            assert "unknown tool" not in result


class TestAgent:
    """Test Agent class."""

    def test_agent_creation(self) -> None:
        """Test creating an Agent instance."""
        agent = Agent(model="gpt-4o-mini")
        assert agent.model == "gpt-4o-mini"
        assert agent.max_rounds == 20

    def test_agent_default_model(self) -> None:
        """Test Agent default model."""
        agent = Agent()
        assert agent.model == "gpt-4o-mini"

    def test_agent_reset(self) -> None:
        """Test resetting agent history."""
        agent = Agent()
        # Simulate some history
        agent.history.append({"role": "user", "content": "test"})
        agent.history.append({"role": "assistant", "content": "response"})
        # Reset
        agent.reset()
        assert len(agent.history) == 0

    @pytest.mark.asyncio
    async def test_agent_chat_empty_history(
        self, mock_env: None, mock_litellm_response: AsyncMock
    ) -> None:
        """Test chat with empty history."""
        agent = Agent(model="gpt-4o-mini")

        with patch("agent.litellm.acompletion", return_value=mock_litellm_response):
            reply = await agent.chat("Hello")

        assert isinstance(reply, str)
        assert len(agent.history) > 0

    @pytest.mark.asyncio
    async def test_agent_chat_with_callbacks(
        self, mock_env: None, mock_litellm_response: AsyncMock
    ) -> None:
        """Test chat with on_tool and on_thought callbacks."""
        agent = Agent(model="gpt-4o-mini")
        thoughts: list[str] = []
        tool_calls: list[tuple[str, dict, str]] = []

        def on_thought(thought: str) -> None:
            thoughts.append(thought)

        def on_tool(name: str, args: dict, result: str) -> None:
            tool_calls.append((name, args, result))

        with patch("agent.litellm.acompletion", return_value=mock_litellm_response):
            reply = await agent.chat("Hello", on_tool=on_tool, on_thought=on_thought)

        assert isinstance(reply, str)


class TestSystemPrompt:
    """Test system prompt building."""

    def test_system_prompt_includes_base(self) -> None:
        """Test that system prompt includes base instructions."""
        from agent import _BASE_SYSTEM_PROMPT

        assert "ReAct" in _BASE_SYSTEM_PROMPT
        assert "Thought" in _BASE_SYSTEM_PROMPT
        assert "Action" in _BASE_SYSTEM_PROMPT
