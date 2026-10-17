import asyncio, websockets, json, sys

async def test():
    uri = "ws://127.0.0.1:8001/sockets/events/fe1cb6e0-4fe9-4633-9583-24e9b8ada2e9"
    try:
        async with websockets.connect(uri, close_timeout=5) as ws:
            # Send the user message
            msg = {"role": "user", "content": [{"type": "text", "text": "Use the test-greeting skill"}]}
            await ws.send(json.dumps(msg))
            print("Message sent, waiting for response...")

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
                        print(f"\n[MESSAGE EVENT] {content[:200]}")
                    elif event_type == "state_update":
                        state = data.get("data", {}).get("state", "")
                        print(f"\n[STATE] {state}")
                        if state in ("STOPPED", "ERROR", "FINISHED"):
                            break
                    elif event_type == "error":
                        print(f"\n[ERROR] {data}")
                        break
                    else:
                        # Print first few of other event types for debugging
                        if message_count <= 5:
                            print(f"\n[{event_type}] {json.dumps(data)[:200]}")

                    if message_count > 200:
                        print("\n[SAFETY] Too many messages, stopping")
                        break
            except websockets.exceptions.ConnectionClosed as e:
                print(f"\n[CONNECTION CLOSED] code={e.code} reason={e.reason}")

            print(f"\n\n=== FULL RESPONSE ({len(full_response)} chars) ===")
            print(full_response[:500])
    except Exception as e:
        print(f"Connection error: {e}")

asyncio.run(test())
