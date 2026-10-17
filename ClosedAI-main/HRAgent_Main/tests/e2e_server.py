"""E2E test of the agent-server (uvicorn) over HTTP.

Boots `python -m runtime.server`, waits for /health, then:
  POST /conversations  (agent with mock LLM + initial user message)
  POST /conversations/{id}/run
  poll GET /conversations/{id} -> FINISHED
  GET  /conversations/{id}/agent_final_response
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

JOB_TMP = Path(os.environ.get("JOB_TMP", "."))
MOCK_BASE = "http://127.0.0.1:8347/v1"
BASE = os.environ.get("SERVER_BASE", "http://127.0.0.1:8331")
API_PREFIX = "/api"
PORT = 8331

HRA = Path(os.environ.get("HRA", ".")).resolve()

PASSED, FAILED = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))


def http(method: str, path: str, payload=None, timeout: float = 60.0):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:  # noqa: BLE001
            return e.code, body


def wait_healthy(tries: int = 30) -> bool:
    for _ in range(tries):
        try:
            status, _ = http("GET", "/health", timeout=3)
            if status == 200:
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return False


def build_conversation_payload():
    # Agent payload with mock LLM (serialize via the real models)
    sys.path.insert(0, str(HRA))
    from models.llm import LLM
    from core.agent import Agent
    from core.workspace import LocalWorkspace
    from pydantic import SecretStr

    llm = LLM(
        model="gpt-4o-mini",
        api_key=SecretStr("sk-mock"),
        base_url=MOCK_BASE,
        usage_id="e2e-server",
        num_retries=0,
        timeout=30,
    )
    agent = Agent(llm=llm)
    payload = {
        "workspace": LocalWorkspace(working_dir=str(JOB_TMP / "ws_server")).model_dump(
            mode="json"
        ),
        "agent": agent.model_dump(
            mode="json",
            exclude_unset=True,
            context={"expose_secrets": "plaintext"},
        ),
        "initial_message": {
            "role": "user",
            "content": [{"type": "text", "text": "Hello from the server test!"}],
            "run": False,
        },
    }
    return payload


def main() -> int:
    print("=" * 70)
    print("SERVER E2E: boot + conversation lifecycle over HTTP")
    print("=" * 70)

    # Boot the server
    py = sys.executable
    env = dict(os.environ)
    env["HRAgentS_SUPPRESS_BANNER"] = "1"
    env.pop("SESSION_API_KEY", None)
    env.pop("OH_SESSION_API_KEYS_0", None)
    proc = subprocess.Popen(
        [py, "-m", "runtime.server", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(HRA),
        env=env,
        stdout=open(JOB_TMP / "server.log", "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    try:
        check("server healthy", wait_healthy(), "(see server.log)")

        payload = build_conversation_payload()
        status, info = http("POST", f"{API_PREFIX}/conversations", payload, timeout=120)
        check("start conversation 201", status in (200, 201), f"status={status}")
        conv_id = (info or {}).get("id") or (info or {}).get("conversation_id")
        check("conversation id returned", bool(conv_id), str(conv_id)[:40])

        if conv_id:
            status, run = http(
                "POST", f"{API_PREFIX}/conversations/{conv_id}/run", {}, timeout=120
            )
            check("run accepted", status == 200, f"status={status}, {str(run)[:80]}")

            # Poll until FINISHED
            final_status = None
            for _ in range(60):
                st, ci = http("GET", f"{API_PREFIX}/conversations/{conv_id}", timeout=30)
                if st == 200 and ci:
                    final_status = ci.get("execution_status")
                    if final_status in ("finished", "FINISHED"):
                        break
                time.sleep(1)
            check("conversation finished", final_status in ("finished", "FINISHED"),
                  f"status={final_status}")

            st, resp = http(
                "GET", f"{API_PREFIX}/conversations/{conv_id}/agent_final_response",
                timeout=30,
            )
            text = ""
            if st == 200 and resp:
                text = (resp.get("text") or resp.get("response") or "")
            check("final response present", bool(text) and "Hello from the server test" in text,
                  text[:100])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("=" * 70)
    print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("FAILED:", ", ".join(FAILED))
        tail = (JOB_TMP / "server.log").read_text(encoding="utf-8", errors="replace")
        print("--- server.log tail ---")
        print("\n".join(tail.splitlines()[-25:]))
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())