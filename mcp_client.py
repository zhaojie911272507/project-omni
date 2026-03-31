"""MCP (Model Context Protocol) integration for Project Omni.

Supports connecting to external MCP servers for extended capabilities.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

load_dotenv()

from agent import tool


# ─────────────────────────────────────────────────────────────────────────────
# MCP Client
# ─────────────────────────────────────────────────────────────────────────────

MCP_SERVERS = os.getenv("MCP_SERVERS", "")


@dataclass
class MCPServer:
    """Represents an MCP server connection."""
    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    process: asyncio.subprocess.Process | None = None
    stdin_writer: asyncio.StreamWriter | None = None
    stdout_reader: asyncio.StreamReader | None = None


class MCPClient:
    """MCP Protocol Client."""

    def __init__(self):
        self.servers: dict[str, MCPServer] = {}
        self._initialize_servers()

    def _initialize_servers(self) -> None:
        """Initialize MCP servers from configuration."""
        if not MCP_SERVERS:
            return

        # Parse server config (comma-separated)
        for i, server_cmd in enumerate(MCP_SERVERS.split(",")):
            server_cmd = server_cmd.strip()
            if not server_cmd:
                continue

            name = f"server_{i}"
            # Simple parsing: command args separated by comma
            parts = [p.strip() for p in server_cmd.split()]
            if parts:
                self.servers[name] = MCPServer(
                    name=name,
                    command=parts,
                    env={},
                )

    async def start_server(self, name: str) -> bool:
        """Start an MCP server process."""
        server = self.servers.get(name)
        if not server:
            return False

        try:
            server.process = await asyncio.create_subprocess_exec(
                *server.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **server.env},
            )
            server.stdin_writer = server.process.stdin
            server.stdout_reader = server.process.stdout
            return True
        except Exception:  # noqa: BLE001
            return False

    async def stop_server(self, name: str) -> None:
        """Stop an MCP server process."""
        server = self.servers.get(name)
        if server and server.process:
            server.process.terminate()
            await server.process.wait()

    async def send_request(
        self,
        server_name: str,
        method: str,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Send a request to an MCP server."""
        server = self.servers.get(server_name)
        if not server or not server.stdin_writer or not server.stdout_reader:
            return {"error": "Server not connected"}

        # Build JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }

        # Send request
        request_str = json.dumps(request) + "\n"
        server.stdin_writer.write(request_str.encode())
        await server.stdin_writer.drain()

        # Read response
        response_line = await server.stdout_reader.readline()
        if not response_line:
            return {"error": "No response"}

        return json.loads(response_line.decode())


# Global MCP client
_mcp_client: MCPClient | None = None


def _get_mcp_client() -> MCPClient:
    """Get or create MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


# ─────────────────────────────────────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="mcp_list_servers",
    description="List configured MCP servers.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def mcp_list_servers() -> str:
    """List configured MCP servers."""
    client = _get_mcp_client()

    if not client.servers:
        return "No MCP servers configured. Set MCP_SERVERS in .env"

    output = "Configured MCP Servers:\n"
    for name, server in client.servers.items():
        output += f"\n- {name}\n"
        output += f"  Command: {' '.join(server.command)}\n"
        output += f"  Status: {'running' if server.process else 'stopped'}\n"

    return output


@tool(
    name="mcp_connect",
    description="Connect to an MCP server.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Server name to connect"},
        },
        "required": ["name"],
    },
)
def mcp_connect(name: str) -> str:
    """Connect to an MCP server."""
    client = _get_mcp_client()

    if name not in client.servers:
        return f"Server '{name}' not found. Use mcp_list_servers to see available servers."

    async def _connect():
        success = await client.start_server(name)
        return success

    success = asyncio.run(_connect())

    if success:
        return f"Connected to {name}"
    return f"Failed to connect to {name}"


@tool(
    name="mcp_disconnect",
    description="Disconnect from an MCP server.",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Server name to disconnect"},
        },
        "required": ["name"],
    },
)
def mcp_disconnect(name: str) -> str:
    """Disconnect from an MCP server."""
    client = _get_mcp_client()

    if name not in client.servers:
        return f"Server '{name}' not found"

    async def _disconnect():
        await client.stop_server(name)

    asyncio.run(_disconnect())
    return f"Disconnected from {name}"


@tool(
    name="mcp_list_tools",
    description="List available tools from an MCP server.",
    parameters={
        "type": "object",
        "properties": {
            "server": {"type": "string", "description": "Server name"},
        },
        "required": ["server"],
    },
)
def mcp_list_tools(server: str) -> str:
    """List tools from an MCP server."""
    client = _get_mcp_client()

    if server not in client.servers:
        return f"Server '{server}' not found"

    async def _list_tools():
        # Ensure connected
        if not client.servers[server].process:
            await client.start_server(server)

        result = await client.send_request(server, "tools/list")
        return result

    result = asyncio.run(_list_tools())

    if "error" in result:
        return f"Error: {result['error']}"

    tools = result.get("result", {}).get("tools", [])
    if not tools:
        return "No tools available"

    output = f"Tools from {server}:\n"
    for t in tools:
        output += f"\n- {t.get('name')}\n"
        if t.get("description"):
            output += f"  {t['description']}\n"

    return output


@tool(
    name="mcp_call_tool",
    description="Call a tool on an MCP server.",
    parameters={
        "type": "object",
        "properties": {
            "server": {"type": "string", "description": "Server name"},
            "tool": {"type": "string", "description": "Tool name to call"},
            "arguments": {
                "type": "string",
                "description": "Tool arguments as JSON string",
            },
        },
        "required": ["server", "tool", "arguments"],
    },
)
def mcp_call_tool(server: str, tool: str, arguments: str) -> str:
    """Call a tool on an MCP server."""
    client = _get_mcp_client()

    if server not in client.servers:
        return f"Server '{server}' not found"

    try:
        args = json.loads(arguments)
    except json.JSONDecodeError:
        return "Invalid JSON in arguments"

    async def _call():
        # Ensure connected
        if not client.servers[server].process:
            await client.start_server(server)

        result = await client.send_request(
            server,
            "tools/call",
            {"name": tool, "arguments": args},
        )
        return result

    result = asyncio.run(_call())

    if "error" in result:
        return f"Error: {result['error']}"

    return json.dumps(result.get("result"), indent=2)