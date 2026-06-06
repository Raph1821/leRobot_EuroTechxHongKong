"""
LLM Provider abstraction — swap between Bedrock, OpenAI, or any
OpenAI-compatible endpoint (EPFL RCP, Ollama, etc.) via config.

Usage:
    from interaction.llm.provider import create_llm_provider
    llm = create_llm_provider()  # reads from env / config
    for token in llm.stream("Hello robot", tools=tools, system_prompt=...):
        print(token, end="")
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    """Unified tool specification (provider-agnostic)."""
    name: str
    description: str
    input_schema: dict = field(default_factory=lambda: {"type": "object", "properties": {}})


@dataclass
class ToolCall:
    """A tool call requested by the model."""
    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    """Result of executing a tool."""
    tool_call_id: str
    content: str


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def stream(
        self,
        user_message: str,
        tools: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        vision_images: list[bytes] | None = None,
    ) -> Generator[str | ToolCall, None, None]:
        """Stream tokens from the model. Yields str for text, ToolCall for tool requests."""
        ...

    @abstractmethod
    def submit_tool_results(
        self, results: list[ToolResult]
    ) -> Generator[str | ToolCall, None, None]:
        """Continue the conversation after tool execution."""
        ...


class BedrockProvider(LLMProvider):
    """AWS Bedrock (converse_stream API) — supports Claude models."""

    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        max_tokens: int = 2048,
    ):
        self.model_id = model_id or os.environ.get(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6"
        )
        self.region = region or os.environ.get("AWS_REGION", "us-west-2")
        self.max_tokens = max_tokens
        self._messages: list[dict] = []
        self._system: list[dict] = []
        self._tools: list[dict] = []
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    def _to_bedrock_tools(self, tools: list[ToolSpec]) -> list[dict]:
        return [
            {
                "toolSpec": {
                    "name": t.name,
                    "description": t.description[:1023],
                    "inputSchema": {"json": t.input_schema},
                }
            }
            for t in tools
        ]

    def stream(
        self,
        user_message: str,
        tools: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        vision_images: list[bytes] | None = None,
    ) -> Generator[str | ToolCall, None, None]:
        self._system = [{"text": system_prompt}] if system_prompt else []
        self._tools = self._to_bedrock_tools(tools) if tools else []

        content: list[dict] = []
        if vision_images:
            for img in vision_images:
                content.append({"image": {"format": "jpeg", "source": {"bytes": img}}})
        content.append({"text": user_message})

        self._messages = [{"role": "user", "content": content}]
        yield from self._run_turn(max_tokens)

    def submit_tool_results(
        self, results: list[ToolResult]
    ) -> Generator[str | ToolCall, None, None]:
        tool_results = [
            {
                "toolResult": {
                    "toolUseId": r.tool_call_id,
                    "content": [{"text": r.content}],
                }
            }
            for r in results
        ]
        self._messages.append({"role": "user", "content": tool_results})
        yield from self._run_turn(self.max_tokens)

    def _run_turn(self, max_tokens: int) -> Generator[str | ToolCall, None, None]:
        request: dict[str, Any] = {
            "modelId": self.model_id,
            "messages": self._messages,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if self._system:
            request["system"] = self._system
        if self._tools:
            request["toolConfig"] = {"tools": self._tools}

        resp = self._get_client().converse_stream(**request)

        assistant_content: list[dict] = []
        current_tool: dict[str, Any] = {}

        for event in resp["stream"]:
            if "contentBlockStart" in event:
                tu = event["contentBlockStart"].get("start", {}).get("toolUse", {})
                if tu:
                    current_tool = {
                        "toolUseId": tu.get("toolUseId"),
                        "name": tu.get("name"),
                        "input_str": "",
                    }

            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    yield delta["text"]
                    assistant_content.append({"text": delta["text"]})
                elif "toolUse" in delta:
                    current_tool["input_str"] += delta["toolUse"].get("input", "")

            elif "contentBlockStop" in event:
                if current_tool.get("name"):
                    raw = current_tool.pop("input_str", "") or "{}"
                    try:
                        tool_input = json.loads(raw)
                    except Exception:
                        tool_input = {}
                    assistant_content.append({
                        "toolUse": {
                            "toolUseId": current_tool["toolUseId"],
                            "name": current_tool["name"],
                            "input": tool_input,
                        }
                    })
                    yield ToolCall(
                        id=current_tool["toolUseId"],
                        name=current_tool["name"],
                        arguments=tool_input,
                    )
                    current_tool = {}

            elif "messageStop" in event:
                pass

        # Merge text blocks for message history
        merged: list[dict] = []
        text_buf = ""
        for blk in assistant_content:
            if "text" in blk:
                text_buf += blk["text"]
            else:
                if text_buf:
                    merged.append({"text": text_buf})
                    text_buf = ""
                merged.append(blk)
        if text_buf:
            merged.append({"text": text_buf})
        if not merged:
            merged.append({"text": ""})
        self._messages.append({"role": "assistant", "content": merged})


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider — works with OpenAI, EPFL RCP, Ollama, etc."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        max_tokens: int = 2048,
    ):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.base_url = base_url or os.environ.get("OPENAI_API_BASE", None)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.max_tokens = max_tokens
        self._messages: list[dict] = []
        self._tools: list[dict] = []
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def _to_openai_tools(self, tools: list[ToolSpec]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]

    def stream(
        self,
        user_message: str,
        tools: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        vision_images: list[bytes] | None = None,
    ) -> Generator[str | ToolCall, None, None]:
        self._messages = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

        self._tools = self._to_openai_tools(tools) if tools else []

        content: Any
        if vision_images:
            import base64
            content = []
            for img in vision_images:
                b64 = base64.b64encode(img).decode()
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
            content.append({"type": "text", "text": user_message})
        else:
            content = user_message

        self._messages.append({"role": "user", "content": content})
        yield from self._run_turn(max_tokens)

    def submit_tool_results(
        self, results: list[ToolResult]
    ) -> Generator[str | ToolCall, None, None]:
        for r in results:
            self._messages.append({
                "role": "tool",
                "tool_call_id": r.tool_call_id,
                "content": r.content,
            })
        yield from self._run_turn(self.max_tokens)

    def _run_turn(self, max_tokens: int) -> Generator[str | ToolCall, None, None]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if self._tools:
            kwargs["tools"] = self._tools

        client = self._get_client()
        response = client.chat.completions.create(**kwargs)

        text_buf = ""
        tool_calls_acc: dict[int, dict] = {}

        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            if delta.content:
                yield delta.content
                text_buf += delta.content

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                    if tc.id:
                        tool_calls_acc[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_acc[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc.function.arguments

        # Build message history
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": text_buf or None}
        if tool_calls_acc:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in tool_calls_acc.values()
            ]
        self._messages.append(assistant_msg)

        # Yield tool calls
        for tc in tool_calls_acc.values():
            try:
                args = json.loads(tc["arguments"])
            except Exception:
                args = {}
            yield ToolCall(id=tc["id"], name=tc["name"], arguments=args)


def create_llm_provider(
    provider: str | None = None, **kwargs
) -> LLMProvider:
    """Factory — create an LLM provider from env config.

    Args:
        provider: "bedrock", "openai", or None (auto-detect from env).
        **kwargs: passed to the provider constructor.

    Env detection logic:
        - If AWS_ACCESS_KEY_ID is set and OPENAI_API_KEY is not → bedrock
        - If OPENAI_API_KEY is set → openai
        - Explicit LLM_PROVIDER env var overrides.
    """
    p = provider or os.environ.get("LLM_PROVIDER", "").lower()
    if not p:
        if os.environ.get("OPENAI_API_KEY"):
            p = "openai"
        else:
            p = "bedrock"

    if p == "bedrock":
        return BedrockProvider(**kwargs)
    elif p in ("openai", "rcp", "ollama"):
        return OpenAIProvider(**kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {p!r}. Use 'bedrock' or 'openai'.")
