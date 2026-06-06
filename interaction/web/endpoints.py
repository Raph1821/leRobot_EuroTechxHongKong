"""
Web API — FastAPI endpoints for voice/text interaction with the robot.

Provides:
  POST /query/stream   — Ask mode (read-only Q&A, SSE)
  POST /command/stream — Agent mode (full tool access, SSE)
  POST /transcribe     — Speech-to-text

Robot-agnostic: mount this router in any FastAPI app.

Usage:
    from fastapi import FastAPI
    from interaction.web.endpoints import create_router

    app = FastAPI()
    app.include_router(create_router())
"""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    text: str
    robot_id: str | None = None


def create_router(
    mcp_url: str | None = None,
    extra_tools: list | None = None,
    tool_handlers: dict | None = None,
) -> APIRouter:
    """Create the interaction API router.

    Args:
        mcp_url: MCP server URL (defaults to DIMOS_MCP_URL env).
        extra_tools: additional tool specs for the LLM.
        tool_handlers: dict of tool_name → callable for non-MCP tools.
    """
    router = APIRouter(tags=["interaction"])

    @router.post("/query/stream")
    async def query_stream(request: QueryRequest):
        """Ask mode — read-only Q&A over MCP (SSE stream)."""
        return _stream_response(request.text, mode="ask", mcp_url=mcp_url,
                                extra_tools=extra_tools, tool_handlers=tool_handlers)

    @router.post("/command/stream")
    async def command_stream(request: QueryRequest):
        """Agent mode — full tool access (SSE stream)."""
        return _stream_response(request.text, mode="agent", mcp_url=mcp_url,
                                extra_tools=extra_tools, tool_handlers=tool_handlers)

    @router.post("/transcribe")
    async def transcribe(request: Request):
        """Speech-to-text endpoint. Accepts raw audio body."""
        audio = await request.body()
        if not audio:
            raise HTTPException(400, "empty audio body")

        content_type = request.headers.get("content-type", "")
        fmt = _detect_audio_format(content_type)
        language = request.headers.get("X-Language", None)

        try:
            from interaction.speech.transcriber import create_transcriber
            t = create_transcriber()
            text = t.transcribe(audio, format=fmt, language=language)
            return {"text": text}
        except Exception as e:
            logger.exception("Transcription failed")
            raise HTTPException(502, f"Transcription failed: {e}")

    return router


def _stream_response(text: str, mode: str, mcp_url=None, extra_tools=None, tool_handlers=None):
    """Create an SSE streaming response from the agent."""
    def generate():
        try:
            from interaction.llm.agent import run_agent_stream
            for token in run_agent_stream(
                text, mode=mode, mcp_url=mcp_url,
                extra_tools=extra_tools, tool_handlers=tool_handlers,
            ):
                yield f"data: {json.dumps(token)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Agent stream error")
            yield f"data: {json.dumps(f'Error: {e}')}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _detect_audio_format(content_type: str) -> str:
    ct = content_type.lower()
    if "webm" in ct:
        return "webm"
    if "mp4" in ct or "m4a" in ct:
        return "mp4"
    if "wav" in ct:
        return "wav"
    if "ogg" in ct:
        return "ogg"
    return "webm"
