"""Project Omni — ReAct Agent Core.

Lightweight agent built on LiteLLM with a decorator-based tool registry.
No heavy framework dependencies; just async function calling in a loop.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import litellm

# ── Tool Registry ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_registry: dict[str, ToolDef] = {}


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
) -> Callable:
    """Decorator — register a callable as an agent tool."""

    def _wrap(fn: Callable) -> Callable:
        _registry[name] = ToolDef(
            name=name,
            description=description,
            parameters=parameters or {"type": "object", "properties": {}},
            fn=fn,
        )
        return fn

    return _wrap


def registered_tools() -> list[dict[str, Any]]:
    return [t.openai_schema() for t in _registry.values()]


def tool_names() -> list[str]:
    return list(_registry.keys())


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    td = _registry.get(name)
    if td is None:
        return f"[error] unknown tool: {name}"
    try:
        result = td.fn(**arguments)
        if asyncio.iscoroutine(result):
            result = await result
        return str(result)
    except Exception as exc:  # noqa: BLE001
        return f"[error] {name}: {exc}"


# ── System Prompt ─────────────────────────────────────────────────────────────

_BASE_SYSTEM_PROMPT = """\
You are **Project Omni**, a personal AI agent with deep autonomous execution capabilities.

## Operating Mode — ReAct
For every user request follow this loop:
1. **Thought** — reason about the current state and decide what to do next.
2. **Action** — call one or more tools.
3. **Observation** — read the tool results and decide whether to continue or reply.
Repeat until you can give a confident, verified final answer.

## Guidelines
- Break complex tasks into small, verifiable steps.
- If a tool call fails, reflect and try an alternative approach — do NOT give up immediately.
- Respond in the **same language** the user uses.
- Be concise; no filler preamble.
"""


def _build_system_prompt() -> str:
    prompt = _BASE_SYSTEM_PROMPT
    soul = Path("SOUL.md")
    if soul.exists():
        prompt += f"\n## User Profile (from SOUL.md)\n{soul.read_text(encoding='utf-8')}\n"
    return prompt


# ── Agent ─────────────────────────────────────────────────────────────────────

ToolCallback = Callable[[str, dict[str, Any], str], None]


@dataclass
class Agent:
    model: str = "gpt-4o-mini"
    history: list[dict[str, Any]] = field(default_factory=list)
    max_rounds: int = 20

    def reset(self) -> None:
        self.history.clear()

    async def chat(
        self,
        user_input: str,
        *,
        on_tool: ToolCallback | None = None,
        on_thought: Callable[[str], None] | None = None,
    ) -> str:
        """Run one full ReAct loop and return the final text reply."""
        if not self.history:
            self.history.append({"role": "system", "content": _build_system_prompt()})
        self.history.append({"role": "user", "content": user_input})

        tools = registered_tools()

        for _ in range(self.max_rounds):
            resp = await litellm.acompletion(
                model=self.model,
                messages=self.history,
                tools=tools or None,
                tool_choice="auto" if tools else None,
                temperature=0.2,
            )
            msg = resp.choices[0].message

            # Build serialisable assistant message
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            self.history.append(assistant_msg)

            # Surface intermediate thoughts (content alongside tool_calls)
            if msg.content and msg.tool_calls and on_thought:
                on_thought(msg.content)

            # No tool calls → final answer
            if not msg.tool_calls:
                return msg.content or ""

            # Execute every tool call
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                result = await execute_tool(fn_name, fn_args)
                if on_tool:
                    on_tool(fn_name, fn_args, result)
                self.history.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        return "⚠️ Reached maximum reasoning rounds without a final answer."
