"""Project Omni — CLI entry point.

Usage:
    python main.py                  # default model: gpt-4o-mini
    python main.py gpt-4o           # use GPT-4o
    python main.py deepseek/deepseek-chat   # use DeepSeek via LiteLLM
    python main.py ollama/llama3    # local model via Ollama
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("omni.cli")

import tools  # noqa: E402, F401 — side-effect: registers built-in tools
from agent import Agent, tool_names  # noqa: E402

_browser_ok = False
try:
    import tools_browser  # noqa: F401

    _browser_ok = True
except Exception:  # noqa: BLE001
    log.debug("Browser tool not available")


# ── Pretty CLI callbacks ─────────────────────────────────────────────────────


def _on_tool(name: str, args: dict, result: str) -> None:
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    print(f"  🔧 {name}({args_str})")
    preview = result[:500] + ("…" if len(result) > 500 else "")
    for line in preview.splitlines():
        print(f"     {line}")


def _on_thought(thought: str) -> None:
    for line in thought.splitlines():
        print(f"  💭 {line}")


# ── Main loop ────────────────────────────────────────────────────────────────


async def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else "gpt-4o-mini"
    agent = Agent(model=model)

    names = tool_names()
    print(f"🤖 Project Omni (model: {model})")
    print(f"   Tools: {', '.join(names)}")
    if not _browser_ok:
        print(
            "   ⚠  browser tool unavailable (pip install playwright && playwright install chromium)"
        )
    print("   Type 'exit' to quit, '/clear' to reset context.\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Bye!")
            break
        if user_input == "/clear":
            agent.reset()
            print("(context cleared)\n")
            continue

        reply = await agent.chat(user_input, on_tool=_on_tool, on_thought=_on_thought)
        print(f"\nOmni > {reply}\n")


if __name__ == "__main__":
    asyncio.run(main())
