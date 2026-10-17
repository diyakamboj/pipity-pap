# HRAgent Test Suite

This directory contains the end-to-end test harness for the HRAgent project. All tests run against a local **mock OpenAI-compatible LLM server** (port 8347) because the user's API keys are blocked at the account level.

## Test Files

| File | Purpose |
|------|---------|
| `mock_llm.py` | FastAPI mock LLM server — deterministic responses via message markers |
| `e2e_driver.py` | Core e2e tests (22 checks): basic conversation, tool calling, streaming, error handling, retries |
| `e2e_driver2.py` | Extended e2e tests (19 checks): skills, subagents, MCP, plugins, memory/context |
| `e2e_server.py` | HTTP agent-server lifecycle tests: boot → POST /conversations → /run → poll → final response |
| `smoke.py` | Import verification (75 modules) for the flattened package structure |
| `lazy_check.py` | Runtime verification (42 checks) of `__getattr__` re-exports |
| `mcp_echo_server.py` | Tiny FastMCP stdio server for MCP integration tests |

## Running the Tests

### Prerequisites
```bash
cd HRAgent_Main
uv sync --dev  # installs test dependencies (pytest, etc.)
```

### 1. Start the Mock LLM Server (required for e2e tests)
```bash
# Terminal 1: runs on http://127.0.0.1:8347
PYTHONPATH=. uv run python tests/mock_llm.py
```

### 2. Run Smoke Tests (no mock needed)
```bash
PYTHONPATH=. uv run python tests/smoke.py
```

### 3. Run Lazy Check (no mock needed)
```bash
PYTHONPATH=. uv run python tests/lazy_check.py
```

### 4. Run E2E Drivers (mock required)
```bash
# Set JOB_TMP to this tests directory for workspace isolation
JOB_TMP=$(pwd)/tests PYTHONPATH=. uv run python tests/e2e_driver.py
JOB_TMP=$(pwd)/tests PYTHONPATH=. uv run python tests/e2e_driver2.py
```

### 5. Run Server E2E Test (mock required)
```bash
# Set HRA to project root for imports
HRA=$(pwd) JOB_TMP=$(pwd)/tests PYTHONPATH=. uv run python tests/e2e_server.py
```

### 6. Run All via Pytest
```bash
# Configure pytest to find tests here
uv run pytest tests/ -v
```

## Mock LLM Control Markers

Insert these in the **last user/assistant message** to control the mock:

| Marker | Effect |
|--------|--------|
| `[[TOOL:name:{"arg":"val"}]]` | Forces a tool call to `name` with JSON args |
| `[[TOOL_ANY]]` | Calls the first declared tool with `{}` |
| `[[FAIL]]` | Returns HTTP 500 "mock forced failure" |
| `[[FAIL_ONCE]]` | Fails first request with marker, then succeeds |
| `[[RAISE]]` | Returns truncated SSE stream (partial output) |
| (none) | Echoes message with "Echo: " prefix |

## Example Test Flow

```bash
# Terminal 1: start mock
PYTHONPATH=. uv run python tests/mock_llm.py

# Terminal 2: run full suite
JOB_TMP=$(pwd)/tests PYTHONPATH=. uv run python tests/smoke.py
JOB_TMP=$(pwd)/tests PYTHONPATH=. uv run python tests/lazy_check.py
JOB_TMP=$(pwd)/tests PYTHONPATH=. uv run python tests/e2e_driver.py
JOB_TMP=$(pwd)/tests PYTHONPATH=. uv run python tests/e2e_driver2.py
HRA=$(pwd) JOB_TMP=$(pwd)/tests PYTHONPATH=. uv run python tests/e2e_server.py
```

## Notes

- Workspace directories (`ws_basic`, `ws_tool`, etc.) are created under `JOB_TMP`
- The mock server is stateless except for `[[FAIL_ONCE]]` counter
- All tests are deterministic — no live LLM calls
- See `e2e_driver.py` for detailed check descriptions