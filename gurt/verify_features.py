"""Verification script for Gurt Multi-Chat Navigation, Persistent Messages, Model Switching, and Persistent Memory.
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from gurt.api.server import app
from gurt.db import init_db, get_connection

init_db()
client = TestClient(app)

def test_conversations_api():
    print("[1/4] Testing Conversation Creation and Multi-Chat List...")
    # 1. Create two distinct conversations
    res1 = client.post("/api/conversations", json={"title": "Speaker Outreach Coordination"})
    assert res1.status_code == 200, f"Failed to create conv 1: {res1.text}"
    c1 = res1.json()
    assert "id" in c1
    print(f" -> Created Conversation 1: {c1['id']} ('{c1['title']}')")

    res2 = client.post("/api/conversations", json={"title": "Catering and Budget Planning"})
    assert res2.status_code == 200, f"Failed to create conv 2: {res2.text}"
    c2 = res2.json()
    print(f" -> Created Conversation 2: {c2['id']} ('{c2['title']}')")

    # 2. List conversations
    res_list = client.get("/api/conversations")
    assert res_list.status_code == 200
    convs = res_list.json()
    conv_ids = [c["id"] for c in convs]
    assert c1["id"] in conv_ids and c2["id"] in conv_ids
    print(f" -> Listed {len(convs)} conversations from SQLite successfully.")
    return c1["id"], c2["id"]

def test_persistent_messages(conv1_id, conv2_id):
    print("\n[2/4] Testing Persistent Message History Across Sessions...")
    # Send message in Thread 1
    msg1_text = "Who are our confirmed speakers for the workshop?"
    res_chat1 = client.post("/api/chat", json={
        "message": msg1_text,
        "conversation_id": conv1_id,
        "model": "semantic-engine"
    })
    assert res_chat1.status_code == 200
    chat1_data = res_chat1.json()
    print(f" -> Chat 1 response received (model: {chat1_data.get('model_used')})")

    # Send message in Thread 2
    msg2_text = "What is our catering budget allocated per head?"
    res_chat2 = client.post("/api/chat", json={
        "message": msg2_text,
        "conversation_id": conv2_id,
        "model": "semantic-engine"
    })
    assert res_chat2.status_code == 200
    chat2_data = res_chat2.json()
    print(f" -> Chat 2 response received (model: {chat2_data.get('model_used')})")

    # Verify messages in Thread 1
    res_msgs1 = client.get(f"/api/conversations/{conv1_id}/messages")
    assert res_msgs1.status_code == 200
    msgs1 = res_msgs1.json()
    contents1 = [m["content"] for m in msgs1]
    assert any(msg1_text in c for c in contents1), "User message missing from Thread 1 history"
    print(f" -> Thread 1 persisted {len(msgs1)} messages correctly in SQLite.")

    # Verify messages in Thread 2 are isolated from Thread 1
    res_msgs2 = client.get(f"/api/conversations/{conv2_id}/messages")
    assert res_msgs2.status_code == 200
    msgs2 = res_msgs2.json()
    contents2 = [m["content"] for m in msgs2]
    assert any(msg2_text in c for c in contents2), "User message missing from Thread 2 history"
    assert not any(msg1_text in c for c in contents2), "Thread isolation violated! Message from Thread 1 leaked to Thread 2."
    print(f" -> Thread 2 persisted {len(msgs2)} messages with full thread isolation.")

def test_model_switching(conv_id):
    print("\n[3/4] Testing Model Switching Dropdown & Route Dispatch...")
    # 1. Models endpoint
    res_models = client.get("/api/models")
    assert res_models.status_code == 200
    models = res_models.json()
    model_ids = [m["id"] for m in models]
    print(f" -> Available models in selector: {model_ids}")
    assert "gemini-3.8-flash" in model_ids
    assert "semantic-engine" in model_ids

    # 2. Dispatch with local dynamic semantic engine
    res_sem = client.post("/api/chat", json={
        "message": "Summarize our event brief and goals",
        "conversation_id": conv_id,
        "model": "semantic-engine"
    })
    assert res_sem.status_code == 200
    assert "semantic-engine" in res_sem.json().get("model_used", "")
    print(f" -> Dispatched using semantic-engine: model_used = {res_sem.json().get('model_used')}")

def test_persistent_memory():
    print("\n[4/4] Testing Persistent Organizer Memory & Preferences...")
    # 1. Save new memory fact via API
    res_save = client.post("/api/memories", json={
        "key": "strict_vegan_quota",
        "value": "Always order at least 20% certified vegan boxed lunches.",
        "category": "dietary_rule"
    })
    assert res_save.status_code == 200
    mem = res_save.json()
    assert mem["key"] == "strict_vegan_quota"
    print(f" -> Saved memory fact: '{mem['key']}' = '{mem['value']}'")

    # 2. Retrieve memories
    res_list = client.get("/api/memories")
    assert res_list.status_code == 200
    mems = res_list.json()
    keys = [m["key"] for m in mems]
    assert "strict_vegan_quota" in keys
    print(f" -> Successfully retrieved {len(mems)} persistent organizer memories from SQLite.")

    # 3. Verify memory is injected into orchestrator system prompt
    from gurt.orchestrator import get_system_instruction
    sys_prompt = get_system_instruction()
    assert "strict_vegan_quota" in sys_prompt
    assert "20% certified vegan" in sys_prompt
    print(" -> Verified persistent memory fact dynamically injected into orchestrator system prompt!")

    # 4. Clean up test memory item
    del_res = client.delete(f"/api/memories/{mem['id']}")
    assert del_res.status_code == 200
    print(f" -> Deleted test memory item {mem['id']}.")

if __name__ == "__main__":
    c1, c2 = test_conversations_api()
    test_persistent_messages(c1, c2)
    test_model_switching(c1)
    test_persistent_memory()
    print("\n=======================================================")
    print("ALL MULTI-CHAT, PERSISTENCE, & MEMORY CHECKS PASSED!")
    print("=======================================================")
