import asyncio, websockets, json, sys

async def test():
    uri = "ws://127.0.0.1:8001/sockets/events/eb28ef8d-b77d-4d71-9d83-54820fe76733"
    try:
        async with websockets.connect(uri, close_timeout=5) as ws:
            msg = {"role": "user", "content": [{"type": "text", "text": "Use the test-greeting skill"}]}
            await ws.send(json.dumps(msg))
            print("Message sent, waiting for response...", flush=True)

            full_response = ""
            message_count = 0
            try:
                async for raw in ws:
                    message_count += 1
                    data = json.loads(raw)
                    event_type = data.get("type", "")

                    if event_type == "streaming_delta":
                        delta = data.get("data", {}).get("delta", "")
                        full_response += delta
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                    elif event_type == "message":
                        content = data.get("data", {}).get("content", "")
                        if content and not full_response:
                            full_response = content
                        print(f"\n[MESSAGE] {content[:300]}", flush=True)
                    elif event_type == "state_update":
                        state = data.get("data", {}).get("state", "")
                        print(f"\n[STATE] {state}", flush=True)
                        if state in ("STOPPED", "ERROR", "FINISHED"):
                            break
                    elif event_type == "error":
                        print(f"\n[ERROR] {data}", flush=True)
                        break
                    elif message_count <= 8:
                        print(f"\n[{event_type}] keys={list(data.get('data',{}).keys())}", flush=True)

                    if message_count > 300:
                        print("\n[SAFETY] Too many messages, stopping", flush=True)
                        break
            except websockets.exceptions.ConnectionClosed as e:
                print(f"\n[CLOSED] code={e.code} reason={e.reason}", flush=True)

            print(f"\n\n=== RESULT ({len(full_response)} chars) ===", flush=True)
            print(full_response[:500] if full_response else "(no streaming response)", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)

asyncio.run(test())
