"""Minimal WS probe: connect to an existing conversation and print first N events."""
import asyncio
import json
import sys

import websockets

conv_id = sys.argv[1] if len(sys.argv) > 1 else None
count = int(sys.argv[2]) if len(sys.argv) > 2 else 20
url = f"ws://127.0.0.1:8001/sockets/events/{conv_id}?resend_mode=all"
print("connecting:", url)


async def main():
    async with websockets.connect(url, max_size=50 * 1024 * 1024, open_timeout=15) as ws:
        print("connected")
        n = 0
        while n < count:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
            except asyncio.TimeoutError:
                print("(timeout waiting)")
                break
            try:
                evt = json.loads(raw)
            except Exception as e:
                print("non-json frame:", raw[:100])
                continue
            kind = evt.get("kind", "?")
            print(f"[{n}] {kind}", {
                k: evt.get(k) for k in ("tool_name", "tool_call_id", "source", "key")
                if evt.get(k) is not None
            } or "")
            n += 1
    print("done", n)


asyncio.run(main())
