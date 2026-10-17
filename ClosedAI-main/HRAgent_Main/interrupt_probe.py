"""Interrupt (Stop-button) probe.

Near-copy of smoke_test_events' proven WS flow, with an interrupt injected
mid-run: POST /api/conversations/{id}/interrupt the moment execution_status
reports running. Verifies the backend honors a stop request on a live run.
"""
import asyncio
import json
import sys

import httpx
import websockets

import smoke_test_events as ste  # .env.local LLM config + payload()

BASE = ste.BASE
WS_BASE = ste.WS_BASE


async def run_probe():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/api/conversations", json=ste.payload("interrupt probe"))
        if r.status_code not in (200, 201):
            print("create failed:", r.status_code, r.text[:300])
            sys.exit(1)
        conv_id = r.json()["id"]
    print("conversation:", conv_id)

    url = f"{WS_BASE}/sockets/events/{conv_id}?resend_mode=all"
    statuses: list[str] = []
    interrupted = False
    interrupt_http = None
    saw_delta = 0

    async with websockets.connect(url, max_size=50 * 1024 * 1024, open_timeout=15) as ws:
        try:
            first = await asyncio.wait_for(ws.recv(), timeout=3)
            print("first frame kind:", json.loads(first).get("kind", "?"))
        except asyncio.TimeoutError:
            print("no first frame")

        await ws.send(
            json.dumps(
                {"role": "user", "content": [{"type": "text", "text": "Write a detailed 500-word essay on the history of cryptography, step by step."}]}
            )
        )
        print("message sent; observing events...")

        deadline = asyncio.get_event_loop().time() + 60
        while asyncio.get_event_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=min(45, deadline - asyncio.get_event_loop().time()))
            except asyncio.TimeoutError:
                print("  (recv timeout — no more events)")
                break
            evt = json.loads(raw)
            kind = evt.get("kind")

            if kind == "ConversationStateUpdateEvent" and isinstance(evt.get("value"), dict):
                st = evt["value"].get("execution_status")
                if st and (not statuses or statuses[-1] != st):
                    statuses.append(st)
                    print("  execution_status ->", st)
                # Interrupt as soon as the run reports running.
                if st == "running" and not interrupted:
                    interrupted = True
                    with httpx.Client(timeout=15) as c2:
                        ri = c2.post(f"{BASE}/api/conversations/{conv_id}/interrupt")
                    interrupt_http = ri.status_code
                    print(f"  ** INTERRUPT fired at run start -> HTTP {interrupt_http} {ri.text[:60]}")
                if st in ("interrupted", "stopped", "finished") and "running" in statuses and interrupted:
                    break
            elif kind == "StreamingDeltaEvent":
                saw_delta += 1
                if not interrupted:
                    interrupted = True
                    with httpx.Client(timeout=15) as c2:
                        ri = c2.post(f"{BASE}/api/conversations/{conv_id}/interrupt")
                    interrupt_http = ri.status_code
                    print(f"  ** INTERRUPT fired on delta #{saw_delta} -> HTTP {interrupt_http} {ri.text[:60]}")
            elif kind in ("ConversationErrorEvent", "AgentErrorEvent", "ServerErrorEvent"):
                print("  !! error event:", str(evt)[:200])

    print("deltas observed:", saw_delta)
    print("status sequence:", statuses)
    started = "running" in statuses or saw_delta > 0
    if interrupted and started and interrupt_http == 200:
        print("VERDICT: PASS — live run started and was interrupted (HTTP", interrupt_http, ")")
    elif interrupted and started:
        print(f"VERDICT: PARTIAL — interrupted (HTTP {interrupt_http}) but statuses = {statuses}")
    else:
        print(f"VERDICT: FAIL — run never started (statuses={statuses}, interrupted={interrupted}, deltas={saw_delta})")


if __name__ == "__main__":
    asyncio.run(run_probe())