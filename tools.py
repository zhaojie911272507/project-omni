"""Built-in local tools for Project Omni.

Covers Phase 1 basics: shell execution, file read/write.
Each function is registered via the @tool decorator.
"""
from __future__ import annotations

import os
import subprocess

from agent import tool


@tool(
    name="shell_exec",
    description=(
        "Execute a shell command and return combined stdout+stderr. "
        "Use this for ls, cat, echo, grep, find, python, git, etc."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to run",
            },
        },
        "required": ["command"],
    },
)
def shell_exec(command: str) -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.getcwd(),
        )
    except subprocess.TimeoutExpired:
        return "[error] command timed out after 60s"

    parts: list[str] = []
    if proc.stdout:
        parts.append(proc.stdout)
    if proc.stderr:
        parts.append(f"[stderr]\n{proc.stderr}")
    if proc.returncode != 0:
        parts.append(f"[exit_code={proc.returncode}]")
    return "\n".join(parts).strip() or "(no output)"


@tool(
    name="read_file",
    description="Read the full contents of a text file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path (absolute or relative)"},
        },
        "required": ["path"],
    },
)
def read_file(path: str) -> str:
    try:
        return open(path, encoding="utf-8").read()  # noqa: SIM115
    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


@tool(
    name="write_file",
    description="Write (create or overwrite) a text file with the given content.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
)
def write_file(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✓ wrote {len(content)} chars → {path}"
    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"
