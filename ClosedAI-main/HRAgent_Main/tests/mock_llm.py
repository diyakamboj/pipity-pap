"""OpenAI-compatible mock LLM server for end-to-end agent testing.

Deterministic control surface:
- If the LAST message (user/assistant) contains  [[TOOL:<name>:<json-args>]]
  the mock emits exactly one tool_call to that tool (args parsed from JSON).
- If it contains  [[TOOL_ANY]]  the mock calls the first tool declared in the
  request with a JSON blob argument.
- Otherwise the mock replies with plain text: the content of the last user
  message is echoed with an "Echo:" prefix (empty if none), which lets tests
  assert the full round-trip.  A message containing [[FAIL]] returns an HTTP
  500, and [[RAISE]] returns malformed output, to exercise error handling.
- stream=true returns SSE chunks ([DONE]-terminated).
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()

TOOL_RE = re.compile(r"\[\[TOOL:([^\]:]+):([^\]]+)\]\]")
_fail_once_counters: dict[str, int] = {}


def _fail_once_should_fail(last: str) -> bool:
    """[[FAIL_ONCE]] fails the first request carrying the marker, then succeeds."""
    if "[[FAIL_ONCE]]" not in last:
        return False
    n = _fail_once_counters.get("fail_once", 0)
    _fail_once_counters["fail_once"] = n + 1
    return n == 0


def _last_text(messages: list[dict]) -> str:
    for msg in reversed(messages):
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):  # content blocks
            parts = [
                c.get("text", "")
                for c in content
                if isinstance(c, dict) and c.get("type") in (None, "text")
            ]
            if parts and any(parts):
                return "\n".join(parts)
    return ""


def _build_tool_call(body: dict[str, Any]) -> dict[str, Any] | None:
    tools = body.get("tools") or []
    if not tools:
        return None
    last = _last_text(body.get("messages") or [])
    m = TOOL_RE.search(last)
    if m:
        name = m.group(1).strip()
        try:
            args = json.loads(m.group(2))
        except json.JSONDecodeError:
            args = {"raw": m.group(2)}
        return {"name": name, "arguments": json.dumps(args)}
    if "[[TOOL_ANY]]" in last:
        first = tools[0]
        name = first.get("function", {}).get("name", "unknown")
        return {"name": name, "arguments": "{}"}
    return None


def _decide(body: dict[str, Any]) -> tuple[str, str | dict[str, Any]]:
    """Return ('text', payload) or ('tool', tool_call)."""
    last = _last_text(body.get("messages") or [])
    if "[[FAIL]]" in last:
        return "text", "OK"
    tool_call = _build_tool_call(body)
    if tool_call:
        return "tool", tool_call
    text = f"Echo: {last}" if last else "OK"
    return "text", text


def _assistant_chunk(delta: dict[str, Any], index: int = 0) -> str:
    data = {
        "id": "chatcmpl-mock",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "mock-llm",
        "choices": [{"index": index, "delta": delta, "finish_reason": None}],
    }
    return f"data: {json.dumps(data)}\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    last = _last_text(body.get("messages") or [])

    if "[[FAIL]]" in last or _fail_once_should_fail(last):
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "mock forced failure", "type": "server_error"}},
        )

    kind, payload = _decide(body)

    if body.get("stream"):
        async def gen():
            if kind == "tool":
                delta = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_mock_1",
                            "type": "function",
                            "function": {
                                "name": payload["name"],
                                "arguments": payload["arguments"],
                            },
                        }
                    ],
                }
                yield _assistant_chunk(delta)
            else:
                text = str(payload)
                if "[[RAISE]]" in last:
                    # Truncate mid-token to exercise partial-output handling.
                    text = "OK"
                for i in range(0, len(text), 3):
                    yield _assistant_chunk({"content": text[i : i + 3]})
                # finish chunk
                data = {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "mock-llm",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(data)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    if kind == "tool":
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_mock_1",
                    "type": "function",
                    "function": {
                        "name": payload["name"],
                        "arguments": payload["arguments"],
                    },
                }
            ],
        }
    else:
        message = {"role": "assistant", "content": str(payload)}

    return JSONResponse(
        {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "mock-llm",
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if kind == "tool" else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
    )


@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [{"id": "mock-llm", "object": "model"}]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8347, log_level="warning")