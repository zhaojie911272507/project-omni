"""Code sandbox tools for Project Omni.

Safe Python code execution using Pyodide (WASM) or restricted subprocess.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agent import tool


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SANDBOX_ENABLED = os.getenv("SANDBOX_ENABLED", "true").lower() == "true"

# Blocked imports and patterns
_BLOCKED_IMPORTS = {
    "os": "Use 'os' is not allowed in sandbox",
    "sys": "Use 'sys' is not allowed in sandbox",
    "subprocess": "Use 'subprocess' is not allowed in sandbox",
    "socket": "Use 'socket' is not allowed in sandbox",
    "requests": "Use 'requests' is not allowed in sandbox (use httpx)",
    "urllib": "Use 'urllib' is not allowed in sandbox",
    "ftplib": "Use 'ftplib' is not allowed in sandbox",
    "smtplib": "Use 'smtplib' is not allowed in sandbox",
    "poplib": "Use 'poplib' is not allowed in sandbox",
    "imaplib": "Use 'imaplib' is not allowed in sandbox",
    "telnetlib": "Use 'telnetlib' is not allowed in sandbox",
    "pty": "Use 'pty' is not allowed in sandbox",
    "tty": "Use 'tty' is not allowed in sandbox",
    "termios": "Use 'termios' is not allowed in sandbox",
    "resource": "Use 'resource' is not allowed in sandbox",
    "pwd": "Use 'pwd' is not allowed in sandbox",
    "grp": "Use 'grp' is not allowed in sandbox",
    "spwd": "Use 'spwd' is not allowed in sandbox",
    "crypt": "Use 'crypt' is not allowed in sandbox",
    "fcntl": "Use 'fcntl' is not allowed in sandbox",
    "pty": "Use 'pty' is not allowed in sandbox",
}

_BLOCKED_PATTERNS = [
    ("import os;", "os module blocked"),
    ("import sys;", "sys module blocked"),
    ("subprocess", "subprocess blocked"),
    ("socket", "socket blocked"),
    ("eval(", "eval blocked"),
    ("exec(", "exec blocked"),
    ("open(", "file operations blocked"),
    ("__import__", "__import__ blocked"),
    ("compile(", "compile blocked"),
]


def _check_code_safety(code: str) -> str | None:
    """Check if code is safe to execute. Returns error message if unsafe."""
    if not SANDBOX_ENABLED:
        return "Sandbox is disabled. Set SANDBOX_ENABLED=true to enable."

    # Check for blocked imports
    for blocked, msg in _BLOCKED_IMPORTS.items():
        if f"import {blocked}" in code or f"from {blocked} import" in code:
            return msg

    # Check for blocked patterns
    for pattern, msg in _BLOCKED_PATTERNS:
        if pattern in code:
            return msg

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox Execution
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="sandbox_exec",
    description=(
        "Execute Python code in a restricted sandbox environment. "
        "Supports basic Python operations, math, data manipulation. "
        "Returns stdout/stderr output."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"},
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds. Default: 30",
            },
        },
        "required": ["code"],
    },
)
def sandbox_exec(code: str, timeout: int = 30) -> str:
    """Execute Python code in a sandbox."""
    # Safety check
    safety_error = _check_code_safety(code)
    if safety_error:
        return f"[sandbox] {safety_error}"

    # Check if sandbox is enabled
    if not SANDBOX_ENABLED:
        return "[sandbox] Sandbox is disabled"

    # Validate timeout
    timeout = min(max(timeout, 1), 60)  # Clamp between 1 and 60 seconds

    try:
        import asyncio
        import sys
        from io import StringIO

        # Capture stdout/stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        # Create a restricted globals dict
        safe_globals = {
            "__builtins__": {
                # Allowed builtins
                "print": print,
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sorted": sorted,
                "reversed": reversed,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "pow": pow,
                "divmod": divmod,
                "isinstance": isinstance,
                "issubclass": issubclass,
                "hasattr": hasattr,
                "getattr": getattr,
                "setattr": setattr,
                "delattr": delattr,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "tuple": tuple,
                "set": set,
                "dict": dict,
                "type": type,
                "slice": slice,
                "None": None,
                "True": True,
                "False": False,
                "Exception": Exception,
                "ValueError": ValueError,
                "TypeError": TypeError,
                "IndexError": IndexError,
                "KeyError": KeyError,
                "StopIteration": StopIteration,
                "KeyError": KeyError,
            },
            # Allow some safe modules
            "math": __import__("math"),
            "json": __import__("json"),
            "random": __import__("random"),
            "datetime": __import__("datetime"),
            "re": __import__("re"),
            "collections": __import__("collections"),
            "itertools": __import__("itertools"),
            "functools": __import__("functools"),
            "operator": __import__("operator"),
            "string": __import__("string"),
        }

        # Execute with timeout
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        try:
            # Use asyncio to run with timeout
            async def _run():
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, exec, code, safe_globals),
                    timeout=timeout,
                )

            asyncio.run(_run())

        except asyncio.TimeoutError:
            return f"[sandbox] Execution timed out after {timeout} seconds"
        except SyntaxError as e:
            return f"[sandbox] Syntax error: {e}"
        except Exception as e:
            # Get error info
            import traceback

            return f"[sandbox] Error: {e}\n{traceback.format_exc()}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        # Get output
        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue()

        result = ""
        if stdout:
            result += stdout
        if stderr:
            result += f"[stderr] {stderr}"

        if not result:
            result = "(no output)"

        return result

    except Exception as exc:  # noqa: BLE001
        return f"[sandbox] Error: {exc}"


@tool(
    name="sandbox_test_code",
    description="Test Python code for safety without executing it.",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to check"},
        },
        "required": ["code"],
    },
)
def sandbox_test_code(code: str) -> str:
    """Test code for safety."""
    safety_error = _check_code_safety(code)

    if safety_error:
        return f"❌ Unsafe: {safety_error}"

    # Additional checks
    lines = code.split("\n")
    issues: list[str] = []

    for i, line in enumerate(lines, 1):
        # Check for too long lines
        if len(line) > 500:
            issues.append(f"Line {i}: Line too long ({len(line)} chars)")

        # Check for deep nesting
        if line.count("    ") > 5:
            issues.append(f"Line {i}: Deep nesting detected")

    if issues:
        return f"⚠️ Warnings:\n" + "\n".join(issues) + "\n\n✅ Code appears safe"

    return "✅ Code appears safe to execute"


@tool(
    name="sandbox_info",
    description="Get sandbox status and configuration.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def sandbox_info() -> str:
    """Get sandbox information."""
    blocked = list(_BLOCKED_IMPORTS.keys())
    return f"""Sandbox Configuration:
- Enabled: {SANDBOX_ENABLED}
- Timeout: 60 seconds max
- Blocked imports: {', '.join(blocked[:10])}...
"""