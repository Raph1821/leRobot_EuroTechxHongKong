"""
MCP Agent — connects any LLM provider to a robot's MCP server,
discovers tools, and runs a streaming agent loop with tool-use handoff.

Supports two modes:
  - "agent": full tool access (can move the robot)
  - "ask": read-only tools only (observation/query)

Usage:
    from interaction.llm.agent import run_agent_stream
    for token in run_agent_stream("find a door", mode="agent"):
        print(token, end="", flush=True)
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator

import httpx

from interaction.llm.provider import (
    LLMProvider,
    ToolCall,
    ToolResult,
    ToolSpec,
    create_llm_provider,
)

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────

MCP_URL = os.environ.get("DIMOS_MCP_URL", "http://localhost:9990/mcp")
MCP_TIMEOUT = float(os.environ.get("DIMOS_MCP_TIMEOUT", "60"))
MAX_TOOL_ITERATIONS = int(os.environ.get("AGENT_MAX_TOOL_ITERATIONS", "8"))

# Tools that physically move the robot — blocked in "ask" mode.
# Adapted for SO-101 stationary arm (no navigation tools, arm-specific actions).
ASK_BLOCKED_TOOLS = {
    # Arm movement actions
    "pick_and_place", "move_to_slot", "sort_medicine", "dispense_pill",
    "execute_trajectory", "home_position", "open_gripper", "close_gripper",
    # Patrol actions
    "start_patrol", "stop_patrol",
    # Legacy mobile-robot tools (kept for compatibility if MCP exposes them)
    "navigate_with_text", "navigate_to_coordinates", "navigate_to_object",
    "begin_exploration", "end_exploration", "follow_person",
    "stop_following", "relative_move", "stop_navigation", "stop_robot",
    "execute_sport_command", "agent_send",
}

# ── System Prompts (override via env or pass directly) ────────

AGENT_SYSTEM_PROMPT = os.environ.get("AGENT_SYSTEM_PROMPT", (
    "You are the AI brain of a SO-101 robotic care arm for elderly medicine management. "
    "You are a STATIONARY robot arm mounted on a table — you cannot move around the room.\n\n"
    "Your capabilities:\n"
    "- Pick and place medicines into sorting slots (A–E: morning, afternoon, evening, as-needed, expired)\n"
    "- Scan medicine labels (OCR) to identify name and expiration date\n"
    "- Count pills and verify correct dosage\n"
    "- Patrol mode: rotate wrist camera to scan the workspace for anomalies\n"
    "- Query your visual memory: recall what medicines you've seen and where\n"
    "- Alert caregivers/hospitals in emergencies (fall detected, help requested)\n\n"
    "Rules:\n"
    "- You CANNOT navigate or move to different rooms. You are fixed in place.\n"
    "- Be concise and helpful. Explain what you're doing.\n"
    "- If asked to do something outside your workspace, explain your limitation.\n"
    "- Confirm before discarding expired medicines."
))

ASK_SYSTEM_PROMPT = os.environ.get("ASK_SYSTEM_PROMPT", (
    "You are the observation/awareness layer of a SO-101 robotic care arm. "
    "You have READ access to the robot's tools: camera feed, workspace memory, "
    "medicine inventory, schedule, and scan history.\n\n"
    "You CANNOT move the arm or execute actions — those tools are disabled. "
    "If the user asks for a physical action, tell them to switch to Agent mode.\n"
    "Be concise and informative."
))


# ── MCP HTTP Client ──────────────────────────────────────────

class MCPClient:
    """Minimal HTTP MCP client (JSON-RPC over HTTP)."""

    def __init__(self, url: str = MCP_URL, timeout: float = MCP_TIMEOUT) -> None:
        self.url = url
        self._next_id = 0
        self._client = httpx.Client(timeout=timeout)

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        body: dict = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params:
            body["params"] = params
        resp = self._client.post(self.url, json=body)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")
        return data.get("result", {})

    def initialize(self) -> dict:
        return self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "interaction-agent", "version": "1.0"},
        })

    def list_tools(self) -> list[dict]:
        return self._rpc("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        parts = [b.get("text", "") for b in content if b.get("type") == "text"]
        return "\n".join(parts) if parts else json.dumps(result)[:400]

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass


# ── Tool filtering ───────────────────────────────────────────

def _filter_tools(mcp_tools: list[dict], mode: str) -> list[dict]:
    if mode != "ask":
        return mcp_tools
    return [t for t in mcp_tools if t["name"] not in ASK_BLOCKED_TOOLS]


def _mcp_to_tool_specs(mcp_tools: list[dict]) -> list[ToolSpec]:
    specs = []
    for t in mcp_tools:
        schema = t.get("inputSchema") or {"type": "object", "properties": {}}
        if "properties" not in schema:
            schema = {**schema, "properties": {}}
        specs.append(ToolSpec(
            name=t["name"],
            description=t.get("description", ""),
            input_schema=schema,
        ))
    return specs


# ── Public Interface ─────────────────────────────────────────

def run_agent_stream(
    user_message: str,
    mode: str = "agent",
    llm: LLMProvider | None = None,
    mcp_url: str | None = None,
    extra_tools: list[ToolSpec] | None = None,
    tool_handlers: dict[str, callable] | None = None,
) -> Generator[str, None, None]:
    """Run an agent loop: LLM ↔ MCP tools until the model stops.

    Args:
        user_message: user's text input.
        mode: "agent" (full tool access) or "ask" (read-only).
        llm: LLM provider instance. Auto-created from env if None.
        mcp_url: MCP server URL. Uses DIMOS_MCP_URL env if None.
        extra_tools: additional ToolSpecs to expose (e.g., cloud-side reads).
        tool_handlers: dict mapping tool names to callables for non-MCP tools.

    Yields:
        Text tokens from the model's response.
    """
    if llm is None:
        llm = create_llm_provider()

    mcp = MCPClient(url=mcp_url or MCP_URL)
    tool_handlers = tool_handlers or {}

    try:
        # Connect to MCP
        try:
            mcp.initialize()
        except Exception as e:
            yield f"⚠ Cannot reach MCP at {mcp.url}. Error: {e}\n"
            return

        mcp_tools = mcp.list_tools()
        if not mcp_tools:
            yield "⚠ MCP returned 0 tools. Is the robot stack fully booted?\n"
            return

        # Filter tools by mode
        mcp_tools = _filter_tools(mcp_tools, mode)
        tool_specs = _mcp_to_tool_specs(mcp_tools)
        if extra_tools:
            tool_specs.extend(extra_tools)

        # Select system prompt
        system_prompt = ASK_SYSTEM_PROMPT if mode == "ask" else AGENT_SYSTEM_PROMPT

        # Initial LLM call
        pending_tool_calls: list[ToolCall] = []
        for item in llm.stream(
            user_message, tools=tool_specs, system_prompt=system_prompt
        ):
            if isinstance(item, str):
                yield item
            elif isinstance(item, ToolCall):
                pending_tool_calls.append(item)

        # Tool loop
        for _ in range(MAX_TOOL_ITERATIONS):
            if not pending_tool_calls:
                return

            # Execute tool calls
            results: list[ToolResult] = []
            for tc in pending_tool_calls:
                yield f"\n[→ {tc.name}({json.dumps(tc.arguments)})]\n"
                try:
                    if tc.name in tool_handlers:
                        output = tool_handlers[tc.name](tc.arguments)
                    else:
                        output = mcp.call_tool(tc.name, tc.arguments)
                except Exception as e:
                    output = f"Error: {e}"
                if len(output) > 4000:
                    output = output[:4000] + "\n[...truncated]"
                results.append(ToolResult(tool_call_id=tc.id, content=output))

            # Feed results back to LLM
            pending_tool_calls = []
            for item in llm.submit_tool_results(results):
                if isinstance(item, str):
                    yield item
                elif isinstance(item, ToolCall):
                    pending_tool_calls.append(item)

        yield "\n[max tool iterations reached]\n"

    finally:
        mcp.close()
