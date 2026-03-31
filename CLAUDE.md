# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI agent
python main.py

# Run server (WeCom/Feishu webhooks)
uvicorn server:app --host 0.0.0.0 --port 8000

# Run tests
pytest tests/

# Run single test file
pytest tests/test_agent.py
pytest tests/test_tools.py -k test_tool_decorator

# Lint and format
ruff check . --fix
ruff format .

# Type check
mypy . --ignore-missing-imports --no-strict-optional

# Install browser tool (optional)
pip install playwright && playwright install chromium
```

## Architecture

**ReAct Agent Loop** (`agent.py`): LiteLLM-based agent with `@tool` decorator registry. Tools are synchronous or async functions that get called via function-calling API. System prompt is built from base ReAct instructions + `SOUL.md` user preferences.

**Tool Layers**:
- `tools.py`: Local execution (shell_exec, read_file, write_file)
- `tools_browser.py`: Web search via DuckDuckGo HTML + Playwright content extraction

**Gateway Layer** (`server.py`): FastAPI app handling WeCom and Feishu webhooks. Each IM user gets a dedicated Agent session keyed by platform+user_id. Encrypted message decryption uses PyCryptodome (AES-CBC).

**Model routing**: Via LiteLLM — `OMNI_MODEL` env var sets default (e.g., `gpt-4o-mini`, `deepseek/deepseek-chat`, `ollama/llama3`).

## Configuration

All config via `.env` file. Key variables:
- `OPENAI_API_KEY` (or other provider keys)
- `OMNI_MODEL`: Default model
- `WECOM_*`: Enterprise WeCom bot credentials
- `FEISHU_*`: Feishu/Lark bot credentials

## Testing Patterns

- `conftest.py` provides fixtures: `mock_env`, `mock_litellm_response`, `mock_litellm_with_tools`
- Tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- Mock `agent.litellm.acompletion` for agent tests
- Tool tests can execute real functions (shell/file ops use tmp_path)

## Extending

Add a new tool by decorating a function in `tools*.py`:

```python
from agent import tool

@tool(
    name="tool_name",
    description="What it does",
    parameters={...}  # JSON Schema, optional
)
def my_tool(arg: str) -> str:
    return result
```

Import the module in `main.py` or `server.py` to register automatically.
