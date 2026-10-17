import requests

payload = {
    "workspace": {"working_dir": "."},
    "agent": {
        "kind": "Agent",
        "llm": {
            "model": "openai/gpt-4o",
            "api_key": "dummy",
            "usage_id": "test"
        },
        "mcp_config": {
            "hr": {
                "transport": "stdio",
                "command": "python",
                "args": ["server.py"]
            }
        }
    }
}

resp = requests.post("http://localhost:8001/api/conversations", json=payload)
print(resp.status_code)
data = resp.json()
agent_def = data.get("agent", {})
mcp = agent_def.get("mcp_config", {})
print("Merged MCP Config Keys:", list(mcp.keys()))
