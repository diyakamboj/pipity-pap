"""Smoke test: create a backend conversation, stream events over WebSocket,
and dump every event kind + key fields. Used to verify the Activity-sidebar
event contract (what the frontend chat-store consumes)."""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import httpx
import websockets

BASE = os.environ.get("HR_BASE", "http://127.0.0.1:8001")
WS_BASE = os.environ.get("HR_WS_BASE", "ws://127.0.0.1:8001")

ENV_LOCAL = Path(__file__).resolve().parent.parent / "frontend" / ".env.local"
ENV = {}
if ENV_LOCAL.exists():
    for line in ENV_LOCAL.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        ENV[k.strip()] = v.strip()

PROVIDER = ENV.get("LLM_PROVIDER", "openai")
if PROVIDER == "openai":
    LLM = {
        "model": ENV.get("OPENAI_MODEL", "gpt-5.2"),
        "api_key": ENV.get("OPENAI_API_KEY"),
        "base_url": ENV.get("OPENAI_BASE_URL"),
        "stream": True,
    }
elif PROVIDER == "tokenrouter":
    LLM = {
        "model": ENV.get("TOKENROUTER_MODEL", "moonshotai/kimi-k3-free"),
        "api_key": ENV.get("TOKENROUTER_API_KEY"),
        "base_url": ENV.get("TOKENROUTER_BASE_URL", "https://api.tokenrouter.com/v1"),
        "stream": True,
    }
else:
    print(f"!! unsupported provider {PROVIDER}; set HR_BASE to a live backend and override LLM inline")
    sys.exit(2)


def payload(prompt: str) -> dict:
    return {
        "workspace": {"working_dir": os.environ.get("HR_WORKSPACE", "workspace/project")},
        "agent": {
            "llm": LLM,
            "tools": [],
            "mcp_config": {},
            "agent_context": {"system_message_suffix": "You are a test agent."},
        },
        "confirmation_policy": {"kind": "ConfirmRisky"},
        "security_analyzer": {"kind": "LLMSecurityAnalyzer"},
        "max_iterations": 20,
    }


def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Reply with exactly: PONG"
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/api/conversations", json=payload(prompt))
        print("create:", r.status_code)
        if r.status_code not in (200, 201):
            print(r.text[:1000])
            sys.exit(1)
        conv = r.json()
    conv_id = conv["id"]
    print("conversation:", conv_id)

    asyncio.run(run_ws(conv_id, prompt))


async def run_ws(conv_id: str, prompt: str):
    url = f"{WS_BASE}/sockets/events/{conv_id}?resend_mode=all"
    print("ws:", url)
    kinds = {}
    counts = {}
    captured: list[dict] = []

    async with websockets.connect(url, max_size=50 * 1024 * 1024, open_timeout=15) as ws:
        # First-frame auth if backend requires it (not configured here).
        try:
            await asyncio.wait_for(ws.recv(), timeout=3)
        except asyncio.TimeoutError:
            pass

        # send the user message
        await ws.send(json.dumps({"role": "user", "content": [{"type": "text", "text": prompt}]}))
        print("sent message")

        deadline = asyncio.get_event_loop().time() + 45
        while asyncio.get_event_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=min(45, deadline - asyncio.get_event_loop().time()))
            except asyncio.TimeoutError:
                break
            try:
                evt = json.loads(raw)
            except Exception:
                continue
            kind = evt.get("kind", "?")
            counts[kind] = counts.get(kind, 0) + 1
            snippet = {
                "kind": kind,
                "source": evt.get("source"),
                "tool_name": evt.get("tool_name"),
                "tool_call_id": evt.get("tool_call_id"),
                "status": evt.get("status"),
                "key": evt.get("key"),
                "summary": (evt.get("summary") or "")[:80],
                "detail": (evt.get("detail") or "")[:60],
            }
            # execution_status for ConversationStateUpdateEvent
            if kind == "ConversationStateUpdateEvent" and isinstance(evt.get("value"), dict):
                snippet["execution_status"] = evt["value"].get("execution_status")
            captured.append(snippet)
            line = f"  [{len(captured):>3}] {kind}"
            for k, v in snippet.items():
                if k != "kind" and v not in (None, "", []):
                    line += f" | {k}={v!r}"
            print(line[:300])

    print("\n=== SUMMARY ===")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")
    out = Path(__file__).parent / "smoke_events_dump.json"
    out.write_text(json.dumps(captured, indent=1, default=str))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
