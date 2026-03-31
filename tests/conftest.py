"""Pytest configuration and fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def soul_md_path(project_root: Path) -> Path:
    """Return path to SOUL.md file."""
    return project_root / "SOUL.md"


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock environment variables for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-for-testing")
    monkeypatch.setenv("OMNI_MODEL", "gpt-4o-mini")


@pytest.fixture
def mock_litellm_response() -> AsyncMock:
    """Mock LiteLLM API response."""
    mock_response = AsyncMock()
    mock_response.choices = [
        type(
            "MockChoice",
            (),
            {
                "message": type(
                    "MockMessage",
                    (),
                    {"content": "Test response", "tool_calls": None},
                )()
            },
        )()
    ]
    return mock_response


@pytest.fixture
def mock_litellm_with_tools(mock_litellm_response: AsyncMock) -> AsyncMock:
    """Mock LiteLLM API response with tool calls."""
    mock_tool_call = type(
        "MockToolCall",
        (),
        {
            "id": "call_123",
            "function": type(
                "MockFunction",
                (),
                {"name": "shell_exec", "arguments": '{"command": "ls -la"}'},
            )(),
        },
    )()
    mock_litellm_response.choices[0].message.tool_calls = [mock_tool_call]
    return mock_litellm_response


@pytest.fixture
def temp_file(tmp_path: Path) -> Path:
    """Create a temporary file for testing."""
    temp = tmp_path / "test_file.txt"
    temp.write_text("test content")
    return temp


@pytest.fixture
def mock_wecom_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock WeCom environment variables."""
    monkeypatch.setenv("WECOM_CORP_ID", "ww_test")
    monkeypatch.setenv("WECOM_APP_SECRET", "test_secret")
    monkeypatch.setenv("WECOM_AGENT_ID", "1000001")
    monkeypatch.setenv("WECOM_TOKEN", "test_token")
    monkeypatch.setenv("WECOM_ENCODING_AES_KEY", "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG")


@pytest.fixture
def mock_feishu_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock Feishu environment variables."""
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("FEISHU_APP_SECRET", "test_secret")
    monkeypatch.setenv("FEISHU_VERIFICATION_TOKEN", "test_token")
