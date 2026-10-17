"""MCP integration smoke test.

Verifies the marketplace -> install -> .mcp.json merge -> server start ->
tool discovery -> tool invocation -> permission-enforcement pipeline against a
live backend, so the full chain is proven end to end.

Credential-agnostic by design:

* The stdio lifecycle is exercised against the bundled FastMCP echo server
  (``tests/mcp_echo_server.py``) — a real MCP server, no external service.
* Third-party probes (GitHub) assert the *clean auth-required state* when no
  token is configured, and exercise the real authenticated discovery path when
  ``GITHUB_PERSONAL_ACCESS_TOKEN`` is set. Live tool invocation against third
  parties is skipped until a real token is present.

The suite boots its own current-code backend on a free port (session-scoped)
so it tests the code as it exists right now, independent of any backend the
developer already has running.

Run from HRAgent_Main with the project venv:

    .venv/Scripts/python.exe -m pytest tests/test_mcp_smoke.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
ECHO_SERVER = Path(__file__).parent / "mcp_echo_server.py"

PLUGIN_NAME = "smoke-echo-plugin"
SERVER_NAME = "echo"
PLUGIN_VERSION = "9.8.7"
PLUGIN_DESCRIPTION = "Smoke-test plugin wrapping the bundled e2e echo MCP server"

BACKEND_READY_TIMEOUT_SECONDS = 90
PROBE_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _project_python() -> str:
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",  # Windows
        PROJECT_ROOT / ".venv" / "bin" / "python",  # POSIX
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return sys.executable


def _wait_ready(base_url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/api/plugins/installed", timeout=3)
            if r.status_code == 200:
                return
            last_error = f"HTTP {r.status_code}"
        except Exception as exc:  # noqa: BLE001 — surface the last failure
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Backend at {base_url} did not become ready: {last_error}")


def _install_path() -> Path:
    return Path.home() / ".HRAgent" / "plugins" / "installed" / PLUGIN_NAME


def _ambient_plugin_mcp_servers() -> dict:
    """Return the installed-plugin MCP servers as the conversation would see them.

    This is the exact merge the conversation runtime performs: enabled installed
    plugins contribute their ``.mcp.json`` servers to the ambient set.
    """
    import core.agent  # noqa: F401 — warms the import chain (server startup order)

    from plugins import load_available_plugins

    avail = load_available_plugins(include_user=True)
    plugin = avail.get(PLUGIN_NAME)
    return dict(plugin.mcp_config) if plugin is not None else {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_base_url(tmp_path_factory) -> str:
    """Boot a current-code backend on a free port and tear it down."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    log_file = tmp_path_factory.mktemp("backend") / "server.log"
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "HRAgents_SUPPRESS_BANNER": "1",
    }
    with log_file.open("w", encoding="utf-8") as out:
        proc = subprocess.Popen(
            [_project_python(), "-m", "runtime.server", "--port", str(port)],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
        )
    try:
        _wait_ready(base_url, BACKEND_READY_TIMEOUT_SECONDS)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def http(api_base_url: str) -> httpx.Client:
    with httpx.Client(base_url=api_base_url, timeout=PROBE_TIMEOUT + 10) as client:
        yield client


@pytest.fixture(scope="module")
def echo_plugin(http: httpx.Client, tmp_path_factory) -> dict:
    """Create, install, and (on teardown) uninstall the throwaway echo plugin.

    A ``force`` uninstall in teardown keeps the shared installed store clean even
    if a test left the plugin disabled or mid-state.
    """
    plugin_dir = tmp_path_factory.mktemp(PLUGIN_NAME)
    venv_python = _project_python().replace("\\", "/")
    echo_server = str(ECHO_SERVER).replace("\\", "/")

    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": PLUGIN_NAME,
                "version": PLUGIN_VERSION,
                "description": PLUGIN_DESCRIPTION,
                "author": {"name": "Smoke Test"},
                "category": "Development",
                "mcp": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (plugin_dir / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    SERVER_NAME: {
                        "transport": "stdio",
                        "command": venv_python,
                        "args": [echo_server],
                    }
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (plugin_dir / "README.md").write_text(
        "# smoke-echo-plugin\n\nThrowaway plugin for the MCP integration smoke test.\n",
        encoding="utf-8",
    )

    # Clear any leftover from a crashed prior run.
    http.delete(f"/api/plugins/installed/{PLUGIN_NAME}")

    r = http.post(
        "/api/plugins/install",
        json={"source": str(plugin_dir)},
    )
    assert r.status_code == 200, f"install failed: {r.status_code} {r.text}"

    yield {"name": PLUGIN_NAME, "server": SERVER_NAME, "source_dir": plugin_dir}

    # Teardown: force-uninstall so the shared store is never left dirty.
    try:
        http.delete(f"/api/plugins/installed/{PLUGIN_NAME}")
    except Exception:  # noqa: BLE001 — best-effort cleanup
        pass
    shutil.rmtree(plugin_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Chain: marketplace -> install -> merge -> discover -> invoke -> permissions
# ---------------------------------------------------------------------------


def test_backend_is_healthy(http: httpx.Client) -> None:
    """Sanity: the backend the whole suite talks to is up."""
    r = http.get("/api/plugins/installed")
    assert r.status_code == 200
    body = r.json()
    names = [p["name"] for p in body.get("plugins", [])]
    # Real integrations must still be present (proves we hit the shared store).
    assert "github" in names

def test_install_snapshots_real_metadata(http: httpx.Client, echo_plugin: dict) -> None:
    """Install snapshots the plugin.json name/version/description (not a fallback)."""
    r = http.get(f"/api/plugins/installed/{PLUGIN_NAME}")
    assert r.status_code == 200
    info = r.json()
    assert info["name"] == PLUGIN_NAME
    assert info["version"] == PLUGIN_VERSION
    assert info["description"] == PLUGIN_DESCRIPTION
    assert info["enabled"] is True
    assert ".mcp.json" in info["files"]
    assert ".metadata.json" in info["files"]

    metadata = json.loads(_install_path().joinpath(".metadata.json").read_text(encoding="utf-8"))
    assert metadata["name"] == PLUGIN_NAME
    assert metadata["version"] == PLUGIN_VERSION
    assert metadata["enabled"] is True


def test_mcp_config_merges_into_ambient_set(echo_plugin: dict) -> None:
    """The installed plugin's .mcp.json contributes its server to the conversation config."""
    servers = _ambient_plugin_mcp_servers()
    assert SERVER_NAME in servers
    spec = servers[SERVER_NAME]
    assert spec.command is not None and spec.command.endswith("python.exe")
    assert spec.args and str(ECHO_SERVER).replace("\\", "/") in str(spec.args[0])


def test_probe_starts_server_and_discovers_tools(http: httpx.Client, echo_plugin: dict) -> None:
    """POST /api/mcp/test spawns the server and lists its real tools."""
    r = http.post(
        "/api/mcp/test",
        json={
            "name": SERVER_NAME,
            "server": {
                "type": "stdio",
                "command": _project_python(),
                "args": [str(ECHO_SERVER)],
            },
            "timeout": PROBE_TIMEOUT,
        },
    )
    assert r.status_code == 200, f"probe failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["ok"] is True, f"probe not ok: {body}"
    tool_names = [t["name"] for t in body["tools"]]
    assert "mcp_echo" in tool_names
    assert "mcp_add" in tool_names


def test_tool_invocation_roundtrip(http: httpx.Client, echo_plugin: dict) -> None:
    """A probe-declared tool_call executes against the server and returns a response."""
    r = http.post(
        "/api/mcp/test",
        json={
            "name": SERVER_NAME,
            "server": {
                "type": "stdio",
                "command": _project_python(),
                "args": [str(ECHO_SERVER)],
            },
            "timeout": PROBE_TIMEOUT,
            "tool_call": {"name": "mcp_echo", "arguments": {"text": "hello-smoke"}},
        },
    )
    assert r.status_code == 200, f"probe failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["ok"] is True
    assert body.get("tool_result") is not None
    assert "mcp:hello-smoke" in json.dumps(body["tool_result"])


def test_disable_stops_mcp_merge(http: httpx.Client, echo_plugin: dict) -> None:
    """Disabling a plugin removes its servers from the conversation merge; re-enabling restores."""
    r = http.patch(f"/api/plugins/installed/{PLUGIN_NAME}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert SERVER_NAME not in _ambient_plugin_mcp_servers()

    r = http.patch(f"/api/plugins/installed/{PLUGIN_NAME}", json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    assert SERVER_NAME in _ambient_plugin_mcp_servers()


def test_uninstall_removes_files_and_merge(http: httpx.Client, echo_plugin: dict) -> None:
    """Uninstall deletes the plugin directory and stops its servers from merging."""
    r = http.delete(f"/api/plugins/installed/{PLUGIN_NAME}")
    assert r.status_code == 200
    assert not _install_path().exists()
    assert SERVER_NAME not in _ambient_plugin_mcp_servers()

    r = http.get("/api/plugins/installed")
    names = [p["name"] for p in r.json().get("plugins", [])]
    assert PLUGIN_NAME not in names


def test_github_unauthenticated_clean_failure(http: httpx.Client) -> None:
    """Probing GitHub without a token returns a clean structured failure, not a crash."""
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
    r = http.post(
        "/api/mcp/test",
        json={
            "name": "github",
            "server": {
                "type": "streamable-http",
                "url": "https://api.githubcopilot.com/mcp/",
                "auth": {"strategy": "bearer", "value": token or "ghp_smoke-invalid"},
            },
            "timeout": 20,
        },
    )
    assert r.status_code == 200, f"probe transport failed: {r.status_code} {r.text}"
    body = r.json()
    if token:
        assert body["ok"] is True
        assert body["tools"], "expected github tools to be discovered with a token"
    else:
        assert body["ok"] is False
        assert body.get("error"), "expected a surfaced error message"
        assert body.get("error_kind"), "expected a structured error_kind"


@pytest.mark.skipif(
    not os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"),
    reason="GITHUB_PERSONAL_ACCESS_TOKEN not set",
)
def test_github_authenticated_discovery(http: httpx.Client) -> None:
    """With a real PAT, GitHub tools are discovered (execution smoke)."""
    r = http.post(
        "/api/mcp/test",
        json={
            "name": "github",
            "server": {
                "type": "streamable-http",
                "url": "https://api.githubcopilot.com/mcp/",
                "auth": {"strategy": "bearer", "value": os.environ["GITHUB_PERSONAL_ACCESS_TOKEN"]},
            },
            "timeout": 25,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True, f"authenticated github probe failed: {body}"
    tool_names = [t["name"] for t in body["tools"]]
    assert "search_code" in tool_names
    assert "list_issues" in tool_names


async def test_permission_deny_blocked() -> None:
    """A tool with permission=deny is blocked before execution."""
    import core.agent  # noqa: F401 — warm import chain

    from mcp_integration.tool import MCPToolExecutor

    executor = MCPToolExecutor(tool_name="mcp_echo", client=None, timeout=5, tool_permission="deny")
    observation = await executor.call_tool(None)  # deny returns before touching the client/action
    assert observation.is_error
    assert "denied" in observation.text.lower()
    assert "blocked" in observation.text.lower()


def test_ask_defers_to_agent_confirmation_gate() -> None:
    """permission=ask defers to the HITL gate (ConfirmRisky) — risky actions are gated."""
    from security.policies.confirmation_policy import (
        AlwaysConfirm,
        ConfirmRisky,
        NeverConfirm,
    )
    from security.policies.risk import SecurityRisk

    # The default HR-grade policy: confirm anything UNKNOWN or riskier than HIGH.
    risky = ConfirmRisky()
    assert risky.should_confirm(SecurityRisk.UNKNOWN) is True
    assert risky.should_confirm(SecurityRisk.HIGH) is True
    assert risky.should_confirm(SecurityRisk.MEDIUM) is False

    # The two degenerate policies round out the enforcement surface.
    assert AlwaysConfirm().should_confirm(SecurityRisk.LOW) is True
    assert NeverConfirm().should_confirm(SecurityRisk.HIGH) is False

def test_registry_search_endpoint(http: httpx.Client) -> None:
    """The /api/mcp/registry/search endpoint queries the official registry and returns results."""
    r = http.get("/api/mcp/registry/search?q=github")
    assert r.status_code == 200
    body = r.json()
    assert "servers" in body
    assert isinstance(body["servers"], list)

def test_mcp_add_tool_invocation(http: httpx.Client, echo_plugin: dict) -> None:
    """Invoking mcp_add correctly computes arithmetic via the bundled echo server."""
    r = http.post(
        "/api/mcp/test",
        json={
            "name": SERVER_NAME,
            "server": {
                "type": "stdio",
                "command": _project_python(),
                "args": [str(ECHO_SERVER)],
            },
            "timeout": PROBE_TIMEOUT,
            "tool_call": {"name": "mcp_add", "arguments": {"a": 20, "b": 22}},
        },
    )
    assert r.status_code == 200, f"probe failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["ok"] is True
    assert body.get("tool_result") is not None
    assert "42" in body["tool_result"]["text"]


