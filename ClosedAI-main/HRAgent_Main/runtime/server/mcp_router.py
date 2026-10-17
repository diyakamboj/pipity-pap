"""MCP router for HRAgents SDK.

Exposes a single endpoint, ``POST /api/mcp/test``, that lets clients verify
a candidate MCP server configuration in isolation -- before persisting it
to settings, where a misconfiguration would otherwise surface only at
conversation start (and there manifest as a noisy traceback that aborts
agent initialization).

The endpoint never mutates server state or touches stored settings: it
spins up the MCP connection, lists the advertised tools, optionally invokes
one caller-chosen tool (``tool_call``), then tears the connection down.
The optional tool call exists because listing tools does not exercise the
credentials many servers only use inside tool handlers (e.g. the Slack MCP
server starts fine with a bogus token); callers must pick a read-only tool.
For OAuth MCP servers, any token/client metadata acquired during the probe is
returned on the success response's ``oauth_state`` field so the caller can
persist it through the settings API under the tested server's ``auth.state``.
"""

from __future__ import annotations

import asyncio
import socket
import time
import uuid
from dataclasses import dataclass, field as dataclass_field
from typing import Annotated, Any, Literal

import httpx
import mcp.types
from fastapi import APIRouter, HTTPException, Request
from fastmcp import Client as AsyncMCPClient
from fastmcp.client.auth.oauth import OAuth as FastMCPOAuth
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import BaseModel, Field, model_validator
from starlette import status

from mcp_integration import create_mcp_tools
from mcp_integration.client import MCPClient
from mcp_integration.config import (
    MCPAuthCredential,
    MCPOAuthAuthCredential,
    MCPOAuthState,
    MCPOAuthStateResponse,
    MCPServer,
    stamp_absolute_token_expiry,
)
from mcp_integration.exceptions import MCPError, MCPTimeoutError
from mcp_integration.oauth_provider_config import get_oauth_callback_port, get_oauth_provider_credentials
from runtime.server._secrets_exposure import get_cipher
from runtime.server.mcp_oauth_store import InMemoryMCPOAuthTokenStore
from runtime.telemetry.logger import get_logger
from utilities.cipher import Cipher


logger = get_logger(__name__)

mcp_router = APIRouter(prefix="/mcp", tags=["MCP"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
#
# We accept one canonical MCPServer instead of the full MCP server map. The UI
# flow this powers ("add a new MCP server") validates one server at a time; the
# route wraps it in a temporary map only at the runtime boundary.

_DEFAULT_SERVER_NAME = "test-server"
_OAUTH_PROBE_JOB_TTL_SECONDS = 15 * 60


class _StdioMCPServerSpec(BaseModel):
    """Legacy stdio MCP server spec accepted by the public REST API."""

    type: Literal["stdio"] = "stdio"
    command: str = Field(..., min_length=1, description="Executable to invoke")
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None

    def to_mcp_server(self) -> MCPServer:
        return MCPServer.model_validate(
            {
                "transport": "stdio",
                "command": self.command,
                "args": self.args,
                "env": self.env,
                "cwd": self.cwd,
            }
        )


class _RemoteMCPServerSpec(BaseModel):
    """Legacy remote MCP server spec accepted by the public REST API."""

    type: Literal["http", "shttp", "streamable-http", "sse"]
    url: str = Field(..., min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    api_key: str | None = Field(
        default=None,
        description=(
            "Deprecated bearer token. Prefer auth.strategy='bearer'. If provided "
            "without auth, sent as 'Authorization: Bearer <token>'."
        ),
    )
    auth: MCPAuthCredential | None = None
    timeout: float | None = None
    sse_read_timeout: float | None = None
    keep_alive: bool | None = None

    @model_validator(mode="after")
    def _reject_ambiguous_auth(self) -> _RemoteMCPServerSpec:
        if self.api_key is not None and self.auth is not None:
            raise ValueError("api_key cannot be combined with auth.")
        if self.api_key is not None and any(
            name.lower() == "authorization" for name in self.headers
        ):
            raise ValueError(
                "api_key cannot be combined with an explicit top-level "
                "'Authorization' header; use auth.strategy='header' instead."
            )
        if self.auth is not None and any(
            name.lower() == "authorization" for name in self.headers
        ):
            raise ValueError(
                "'auth' cannot be combined with an explicit top-level "
                "'Authorization' header; use auth.strategy='header' instead."
            )
        return self

    def to_mcp_server(self) -> MCPServer:
        transport = "http" if self.type == "shttp" else self.type
        data: dict[str, Any] = {
            "url": self.url,
            "transport": transport,
            "headers": self.headers,
            "timeout": self.timeout,
            "sse_read_timeout": self.sse_read_timeout,
            "keep_alive": self.keep_alive,
        }
        if self.auth is not None:
            data["auth"] = self.auth
        elif self.api_key is not None:
            data["auth"] = {"strategy": "bearer", "value": self.api_key}
        return MCPServer.model_validate(data)


MCPTestServerSpec = Annotated[
    _StdioMCPServerSpec | _RemoteMCPServerSpec,
    Field(discriminator="type"),
]


class MCPToolCallSpec(BaseModel):
    """A single tool invocation to run as part of the connection test.

    Listing tools does not exercise the credentials many servers only use
    inside tool handlers, so callers can name one tool to invoke after the
    listing succeeds. Callers are responsible for choosing a read-only tool;
    the endpoint executes it verbatim.
    """

    name: str = Field(..., min_length=1, description="Name of the tool to invoke")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments passed to the tool unchanged.",
    )


class MCPTestRequest(BaseModel):
    """Body for ``POST /api/mcp/test``."""

    name: str = Field(
        default=_DEFAULT_SERVER_NAME,
        min_length=1,
        max_length=128,
        description=(
            "Name to use for the server inside the temporary MCP server map. "
            "Only affects error messages -- does not need to match any "
            "persisted setting."
        ),
    )
    server: MCPTestServerSpec
    timeout: float = Field(
        default=60.0,
        gt=0,
        le=120,
        description="Seconds to wait for connection + tools/list to complete.",
    )
    tool_call: MCPToolCallSpec | None = Field(
        default=None,
        description=(
            "Optional read-only tool to invoke after listing succeeds, so "
            "callers can verify credentials the server only exercises on "
            "tool invocation. Its outcome is reported verbatim in "
            "`tool_result` without affecting `ok`."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_native_server_transport(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        server = value.get("server")
        if not isinstance(server, dict):
            return value
        if "authentication" in server:
            raise ValueError(
                "OAuth authentication metadata belongs under auth.authentication."
            )
        if "type" in server:
            return value
        normalized = dict(value)
        normalized_server = dict(server)
        transport = normalized_server.pop("transport", None)
        if transport is None:
            transport = "stdio" if "command" in normalized_server else "http"
        normalized_server["type"] = transport
        normalized["server"] = normalized_server
        return normalized

    @model_validator(mode="after")
    def _strip_name(self) -> MCPTestRequest:
        # Mirror the validation the MCP server map itself applies to server keys --
        # whitespace-only names would silently bypass min_length=1 above.
        self.name = self.name.strip() or _DEFAULT_SERVER_NAME
        self.resolved_server
        return self

    @property
    def resolved_server(self) -> MCPServer:
        return self.server.to_mcp_server()

    def to_mcp_config(self, *, cipher: Cipher | None = None) -> dict[str, MCPServer]:
        return {self.name: self.resolved_server.with_decrypted_secrets(cipher=cipher)}


class MCPToolCallResult(BaseModel):
    """Verbatim outcome of the requested ``tool_call``.

    The endpoint stays provider-neutral: many servers report upstream
    failures (e.g. Slack's ``{"ok": false, "error": "invalid_auth"}``)
    as ordinary text content with ``isError`` unset, so interpreting the
    payload is the caller's job.
    """

    is_error: bool = Field(description="The MCP-level isError flag of the result.")
    text: str = Field(description="Concatenated text content of the result.")


class MCPTestToolInfo(BaseModel):
    name: str
    description: str | None = None

class MCPTestSuccess(BaseModel):
    """Response when the candidate server connects and lists its tools."""

    ok: Literal[True] = True
    tools: list[MCPTestToolInfo] = Field(
        default_factory=list,
        description="Tools advertised by the MCP server.",
    )
    tool_result: MCPToolCallResult | None = Field(
        default=None,
        description=("Outcome of the requested `tool_call`, when one was supplied."),
    )
    resolved_mcp_servers: list[dict[str, Any]] | None = Field(
        default=None,
        description=(
            "Deprecated compatibility field for older clients that expected "
            "resolved MCP server metadata in test responses."
        ),
    )
    oauth_state: MCPOAuthStateResponse | None = Field(
        default=None,
        description=(
            "Serialized OAuth state acquired or refreshed by the probe. "
            "Clients should persist this under the tested server's auth.state."
        ),
    )


class MCPTestFailure(BaseModel):
    """Response when the candidate server fails to connect or list tools.

    The endpoint returns HTTP 200 in both success and failure cases: a
    failure here is the *expected* outcome of validating a user-supplied
    config, not a server-side error. The structured shape makes it easy
    for the UI to render an actionable message.
    """

    ok: Literal[False] = False
    error: str = Field(description="Human-readable error message.")
    error_kind: Literal["timeout", "connection", "unknown"] = Field(
        description="Coarse error classification, useful for branching UI."
    )


MCPTestResponse = MCPTestSuccess | MCPTestFailure


def _run_tool_call(
    client: MCPClient, spec: MCPToolCallSpec, tools: list[MCPTestToolInfo], timeout: float
) -> MCPToolCallResult:
    """Invoke the requested tool on the connected client.

    Uses ``call_tool_mcp`` (not ``call_tool``, which raises on ``isError``)
    so in-band failures come back as data -- mirrors ``MCPToolExecutor``.
    A timeout is reported as an errored result rather than failing the
    whole test: the server did connect and list, which is still useful.
    """
    if spec.name not in [t.name for t in tools]:
        tool_names = [t.name for t in tools]
        return MCPToolCallResult(
            is_error=True,
            text=(
                f"Tool {spec.name!r} not advertised by server "
                f"(available: {', '.join(tool_names) or 'none'})"
            ),
        )
    try:
        result: mcp.types.CallToolResult = client.call_async_from_sync(
            client.call_tool_mcp,
            name=spec.name,
            arguments=spec.arguments,
            timeout=timeout,
        )
    except TimeoutError:
        return MCPToolCallResult(
            is_error=True,
            text=f"Tool {spec.name!r} call timed out after {timeout} seconds",
        )
    text = "\n".join(
        block.text
        for block in result.content
        if isinstance(block, mcp.types.TextContent)
    )
    return MCPToolCallResult(is_error=bool(result.isError), text=text)


def _probe_mcp_server(
    request: MCPTestRequest,
    cipher: Cipher | None,
) -> MCPTestResponse:
    """Synchronous probe -- safe to run inside ``run_in_executor``.

    ``create_mcp_tools`` already runs its own event loop in a background
    thread via ``MCPClient.call_async_from_sync``. We deliberately do not
    call it from the FastAPI request task; instead the caller hops into a
    threadpool first.
    """

    mcp_config = request.to_mcp_config(cipher=cipher)

    # If the caller passed an already-completed OAuth session (the normal
    # case for "Test connection" on an existing, configured server -- see
    # McpConnection.config on the frontend), seed an ephemeral in-memory
    # token store from it so the probe actually authenticates with that
    # session instead of starting from a blank client and attempting dynamic
    # client registration -- which 404s for any provider that doesn't
    # support DCR (Google, GitHub, ...) even though a perfectly good saved
    # session exists. Nothing here is persisted; the store is thrown away
    # when the probe returns. Servers with no oauth2 auth, or with oauth2
    # auth but no state yet (a brand-new candidate config), get no seeded
    # store and fall through to RuntimeOnlyOAuth's default in-memory store --
    # which still cannot open a browser (see mcp_integration.utils), so a
    # server that genuinely has no session just fails fast and clean here,
    # exactly as it should for a non-interactive probe endpoint.
    # Read from the post-decryption `mcp_config` (not `request.resolved_server`,
    # which is still ciphertext at this point) -- seeding the token store with
    # an encrypted access_token would make every real request to the MCP
    # server carry a bearer token that is literally ciphertext, not a usable
    # credential.
    mcp_oauth_token_storage = None
    server_auth = mcp_config[request.name].auth
    if isinstance(server_auth, MCPOAuthAuthCredential) and server_auth.state is not None:
        mcp_oauth_token_storage = InMemoryMCPOAuthTokenStore(state=server_auth.state)

    try:
        # ``create_mcp_tools`` returns a client that owns a background loop
        # and a (possibly long-lived) subprocess. Use the context-manager
        # form so we always tear it down, even when listing succeeded.
        with create_mcp_tools(
            mcp_config,
            timeout=request.timeout,
            mcp_oauth_token_storage=mcp_oauth_token_storage,
        ) as client:
            tools = [MCPTestToolInfo(name=t.name, description=t.description) for t in client.tools]
            tool_result: MCPToolCallResult | None = None
            if request.tool_call is not None:
                tool_result = _run_tool_call(
                    client,
                    request.tool_call,
                    tools,
                    request.timeout,
                )
            return MCPTestSuccess(
                tools=tools,
                tool_result=tool_result,
                oauth_state=None,
            )
    except MCPTimeoutError as exc:
        logger.info("MCP test timed out for server %r: %s", request.name, exc)
        return MCPTestFailure(error=str(exc), error_kind="timeout")
    except MCPError as exc:
        # ``MCPError("MCP Connection Failure")`` is what client.connect()
        # raises when the underlying fastmcp client fails to start. Surface
        # the root-cause message (e.g. "sh: 1: mcp-server-github: Permission
        # denied") because the wrapper alone isn't useful.
        cause = exc.__cause__ or exc.__context__
        detail = str(cause) if cause else str(exc) or "Failed to connect to MCP server"
        logger.info(
            "MCP test connection failed for server %r: %s", request.name, detail
        )
        return MCPTestFailure(error=detail, error_kind="connection")
    except Exception as exc:  # noqa: BLE001 - we want to surface anything else
        # Any other exception is unexpected but should still return a
        # structured response: the UI can't recover from a 500.
        logger.warning(
            "MCP test failed unexpectedly for server %r",
            request.name,
            exc_info=True,
        )
        return MCPTestFailure(
            error=f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__,
            error_kind="unknown",
        )


@mcp_router.post(
    "/test",
    response_model=MCPTestResponse,
    response_model_exclude_none=True,
    summary="Test an MCP server configuration",
    description=(
        "Attempt to connect to a candidate MCP server and list its tools, "
        "without persisting any settings. Useful for validating user input "
        "in 'add MCP server' flows before storing the config. "
        "For OAuth servers, any acquired state is returned as `oauth_state` "
        "so clients can persist it under the MCP server object's `auth.state`. "
        "Optionally invokes one caller-chosen (read-only) tool via "
        "`tool_call` and reports its outcome in `tool_result`, so callers "
        "can verify credentials that are only exercised on tool invocation. "
        "Encrypted `env`/`headers` values round-tripped from settings are "
        "decrypted before the connection is attempted. "
        "Returns 200 with `ok=false` for connection / timeout failures "
        "(those are expected during validation, not server errors)."
    ),
)
async def test_mcp_server(
    request: MCPTestRequest, http_request: Request
) -> MCPTestResponse:
    """Probe a single MCP server config and report whether it works."""
    # Resolve the cipher here: the threadpool function below must not
    # reach back into ``http_request.app.state``.
    cipher = get_cipher(http_request)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _probe_mcp_server, request, cipher)





# ---------------------------------------------------------------------------
# OAuth authorization jobs
# ---------------------------------------------------------------------------
#
# The marketplace/settings UI drives OAuth servers through a poll-based job:
# POST /oauth/start kicks the flow off and (usually) returns the provider's
# authorization URL for the UI to open in a new tab; GET /oauth/status/{id}
# is polled until the job succeeds or fails. This intentionally reuses
# FastMCP's own OAuthClientProvider (dynamic client registration, PKCE, token
# exchange, and its own localhost callback HTTP server) rather than
# reimplementing any of that -- the only thing overridden is
# ``redirect_handler``, which normally opens a browser on the *server*
# process; here it just hands the URL to the job instead.
#
# Jobs run against an in-memory token store scoped to the job, not the
# settings-backed one: the server being authorized may not be saved yet (the
# user could still be filling out the "Add server" dialog). On success the
# resulting ``oauth_state`` is returned to the caller, which is responsible
# for persisting it via PATCH /settings under the server's ``auth.state`` --
# mirroring how POST /mcp/test already reports (but never persists)
# ``oauth_state``.

_OAUTH_JOB_TTL_SECONDS = 15 * 60
_OAUTH_START_WAIT_SECONDS = 3.0


def _oauth_callback_port() -> int:
    """The shared local callback port every OAuth job binds.

    Read from the centralized OAuth config file on every call (see
    ``mcp_integration.oauth_provider_config``) rather than frozen once at
    import time, so editing that file's ``redirect_uri`` takes effect
    without a server restart -- same as provider client id/secret edits.
    One OAuth job runs at a time (see _supersede_active_oauth_jobs), so a
    single shared port is fine.
    """
    return get_oauth_callback_port()

OAuthJobStatus = Literal["pending", "authorizing", "succeeded", "failed"]
# "not_configured": the integration needs a backend-configured OAuth provider
# app (see mcp_integration.oauth_provider_config) that hasn't been set up.
# "cancelled": superseded by a newer OAuth attempt (see _supersede_active_oauth_job)
# or explicitly cancelled. Distinct from "connection"/"timeout"/"unknown" so
# the UI can say exactly what happened instead of a generic OAuth failure.
OAuthErrorKind = Literal[
    "timeout", "connection", "not_configured", "cancelled", "port_busy", "unknown"
]


class MCPOAuthProviderNotConfiguredError(Exception):
    """Raised when an integration needs a backend OAuth provider app that
    has no credentials configured (see ``oauth_provider_config``)."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(
            f"This integration requires a {provider!r} OAuth application "
            "configured on the backend, but none was found. An "
            f"administrator must add a {provider!r} entry to "
            "~/.HRAgent/oauth_providers.json (see "
            "config/oauth_providers.example.json) before this integration "
            "can be connected."
        )


@dataclass
class _OAuthJob:
    status: OAuthJobStatus = "pending"
    authorization_url: str | None = None
    callback_ready: bool = False
    tools: list[MCPTestToolInfo] | None = None
    oauth_state: MCPOAuthState | None = None
    error: str | None = None
    error_kind: OAuthErrorKind | None = None
    created_at: float = dataclass_field(default_factory=time.time)
    updated: asyncio.Event = dataclass_field(default_factory=asyncio.Event)
    # The connection/server this job authorizes, used to prevent two jobs
    # racing for the same server (they'd fight over the shared callback
    # port) and to let a fresh Connect/Re-authenticate click supersede a
    # stale one instead of just piling up forever. None for ad hoc probes
    # (e.g. the "Add custom server" dialog) that aren't tied to a saved
    # connection.
    server_key: str | None = None
    cancelled: bool = False


_OAUTH_JOBS: dict[str, _OAuthJob] = {}
_OAUTH_TASKS: dict[str, asyncio.Task[None]] = {}


async def _prune_oauth_jobs() -> None:
    """Drop expired jobs, waiting for any still-running task to actually
    unwind (see _cancel_oauth_job) rather than firing a cancel and moving
    on -- a stale job's callback server can otherwise still be mid-shutdown
    when the very next call starts a new one on the same port.
    """
    cutoff = time.time() - _OAUTH_JOB_TTL_SECONDS
    expired_ids = [jid for jid, job in _OAUTH_JOBS.items() if job.created_at < cutoff]
    for job_id in expired_ids:
        await _cancel_oauth_job(job_id, reason="Expired.")
        _OAUTH_JOBS.pop(job_id, None)


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


async def _wait_for_port_release(port: int, *, timeout: float) -> bool:
    """Poll until ``port`` can be bound again, or ``timeout`` elapses.

    FastMCP's OAuth callback server only gives its own uvicorn instance a
    100ms grace period to shut down before force-cancelling it (see
    ``fastmcp.client.auth.oauth.OAuth.callback_handler``), which is often not
    enough time for the socket to actually close. A caller that starts a new
    callback server on the same port before it's released hits uvicorn's own
    ``Server.startup()`` bind failure, which calls ``sys.exit(1)`` -- raising
    ``SystemExit`` right out of the new job (see ``_classify_oauth_error``'s
    "port_busy" case). Waiting here, actively confirming the port is free
    rather than guessing a fixed delay, makes that far less likely.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if await asyncio.to_thread(_port_is_free, port):
            return True
        await asyncio.sleep(0.15)
    return False


async def _cancel_oauth_job(
    job_id: str, *, reason: str, error_kind: OAuthErrorKind = "cancelled"
) -> None:
    """Cancel a job's background task and wait for it to actually finish
    unwinding -- including releasing the shared OAuth callback port --
    before returning.

    A fire-and-forget ``task.cancel()`` schedules cancellation but returns
    immediately -- the coroutine (and whatever it holds, notably the shared
    OAuth callback port) may not have released its resources yet. A caller
    that immediately starts a *new* job on the same port can then lose that
    race and crash the new job (or worse -- see the SystemExit handling in
    _run_oauth_job). Awaiting the cancelled task, then actively confirming
    the port is free, closes that window.
    """
    job = _OAUTH_JOBS.get(job_id)
    task = _OAUTH_TASKS.pop(job_id, None)
    if job is not None and job.status in ("pending", "authorizing"):
        job.cancelled = True
        job.status = "failed"
        job.error = reason
        job.error_kind = error_kind
        job.updated.set()
    if task is None or task.done():
        return
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.CancelledError:
        pass  # expected: this is exactly what we just requested
    except TimeoutError:
        logger.warning(
            "MCP OAuth job %s did not finish unwinding within 5s of "
            "cancellation",
            job_id,
        )
    except Exception:
        # The task's own cleanup raised something else while unwinding.
        # Already logged (if it got that far) inside _run_oauth_job's own
        # except block; nothing more to do here.
        pass

    if not await _wait_for_port_release(_oauth_callback_port(), timeout=10.0):
        logger.warning(
            "MCP OAuth job %s: callback port %d still in use 10s after "
            "cancellation -- the next job to start may fail with "
            "'port_busy' until it clears.",
            job_id,
            _oauth_callback_port(),
        )


class _JobOAuth(FastMCPOAuth):
    """FastMCP's ``OAuth`` provider, adapted to a poll-based web job.

    Everything (DCR, PKCE, token exchange, the local callback HTTP server
    that receives the provider's redirect) is inherited unchanged. Only
    ``redirect_handler`` is overridden: instead of calling
    ``webbrowser.open()`` on the backend process, it publishes the
    authorization URL onto the job so ``/oauth/status`` can hand it to the
    caller, who opens it in the *user's* browser.
    """

    def __init__(self, job: _OAuthJob, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._job = job

    async def redirect_handler(self, authorization_url: str) -> None:
        self._job.authorization_url = authorization_url
        self._job.status = "authorizing"
        self._job.callback_ready = True
        self._job.updated.set()
        self._job.updated = asyncio.Event()

    # GitHub's token endpoint (github.com/login/oauth/access_token) replies
    # application/x-www-form-urlencoded unless the request explicitly asks
    # for JSON -- the MCP SDK's OAuth2 client (mcp.client.auth.oauth2) never
    # sends that header, so its `OAuthToken.model_validate_json` call on a
    # form-encoded body fails with "Invalid JSON". Every other provider we
    # support (Google, Slack, Linear) already replies JSON regardless, so
    # this only needs to widen the Accept header, never change behavior for
    # them. See https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps#response
    async def _exchange_token_authorization_code(self, *args: Any, **kwargs: Any) -> httpx.Request:
        request = await super()._exchange_token_authorization_code(*args, **kwargs)
        request.headers["Accept"] = "application/json"
        return request

    async def _refresh_token(self, *args: Any, **kwargs: Any) -> httpx.Request:
        request = await super()._refresh_token(*args, **kwargs)
        request.headers["Accept"] = "application/json"
        return request


def _classify_oauth_error(exc: BaseException) -> OAuthErrorKind:
    if isinstance(exc, MCPOAuthProviderNotConfiguredError):
        return "not_configured"
    if isinstance(exc, SystemExit):
        # Uvicorn's own Server.startup() calls sys.exit(1) on a bind
        # failure -- the shared OAuth callback port (see
        # _oauth_callback_port) is still held by a job that hasn't
        # finished releasing it yet, most often right after cancelling a
        # previous one. See _cancel_oauth_job's port-release wait.
        return "port_busy"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, (MCPError, httpx.HTTPError, OSError, ConnectionError)):
        return "connection"
    return "unknown"


async def _run_oauth_job(
    job_id: str,
    server: MCPServer,
    cipher: Cipher | None,
    tool_call: MCPToolCallSpec | None,
) -> None:
    job = _OAUTH_JOBS[job_id]
    try:
        decrypted = server.with_decrypted_secrets(cipher=cipher)
        oauth_cred = decrypted.oauth_auth
        if oauth_cred is None or decrypted.url is None:
            raise ValueError(
                "server.auth.strategy must be 'oauth2' with a remote 'url' to "
                "start an OAuth job"
            )

        auth_meta = oauth_cred.authentication
        scopes = auth_meta.scopes if auth_meta else None
        client_name = (auth_meta.client_name if auth_meta else None) or "HRAgent"
        additional_metadata = dict(auth_meta.additional_client_metadata or {}) if auth_meta else {}

        # Resolve the pre-registered app credentials this provider needs.
        # ``provider`` (set on the integration's .mcp.json template, never
        # by the frontend) names an entry in the backend-only OAuth provider
        # config -- see mcp_integration/oauth_provider_config.py. A caller-
        # supplied client_id (legacy/custom servers) still wins if present,
        # but nothing in the current marketplace catalog sends one anymore.
        client_id: str | None = auth_meta.client_id if auth_meta else None
        client_secret: str | None = (
            auth_meta.client_secret.get_secret_value()
            if auth_meta and auth_meta.client_secret is not None
            else None
        )
        if not client_id and auth_meta and auth_meta.provider:
            provider_creds = get_oauth_provider_credentials(auth_meta.provider)
            if provider_creds is None:
                raise MCPOAuthProviderNotConfiguredError(auth_meta.provider)
            client_id = provider_creds.client_id
            client_secret = (
                provider_creds.client_secret.get_secret_value()
                if provider_creds.client_secret is not None
                else None
            )

        # Dynamically-registered MCP clients are public (PKCE-only, no
        # client_secret) unless a pre-registered confidential client_id was
        # resolved above. Without this, some authorization servers (e.g.
        # Linear) register a confidential client by default, and the later
        # token exchange -- which always sends the PKCE code_verifier --
        # gets rejected with "must not use multiple authentication methods"
        # because it also carries client credentials.
        if not client_id:
            additional_metadata.setdefault("token_endpoint_auth_method", "none")

        token_store = InMemoryMCPOAuthTokenStore()
        job_oauth = _JobOAuth(
            job,
            mcp_url=decrypted.url,
            scopes=scopes,
            client_name=client_name,
            token_storage=token_store,
            additional_client_metadata=additional_metadata or None,
            # A fixed port (not FastMCP's default random one) is required for
            # any provider that validates redirect_uri by exact match against
            # a pre-registered value (e.g. Slack) rather than allowing any
            # localhost loopback port (Google Desktop-app clients, Linear's
            # DCR). Provider apps must register the centralized config
            # file's redirect_uri exactly (see oauth_provider_config.py).
            callback_port=_oauth_callback_port(),
        )

        # Providers that don't support dynamic client registration (e.g.
        # Google) require a pre-registered client id/secret; when resolved
        # above, seed it directly so OAuthClientProvider skips DCR.
        if client_id:
            await job_oauth.token_storage_adapter.set_client_info(
                OAuthClientInformationFull(
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uris=[f"http://localhost:{job_oauth.redirect_port}/callback"],
                    grant_types=["authorization_code", "refresh_token"],
                    response_types=["code"],
                    # Without this, mcp.client.auth.oauth2's prepare_token_auth
                    # only attaches client_secret when token_endpoint_auth_method
                    # is explicitly "client_secret_basic" or "client_secret_post"
                    # -- leaving it unset drops the secret from the token
                    # exchange entirely ("client_secret is missing", even
                    # though we have one).
                    token_endpoint_auth_method=(
                        "client_secret_post" if client_secret else "none"
                    ),
                )
            )

        # FastMCP's own OAuth callback wait allows up to 5 minutes for the
        # user to complete the provider's login/consent screens; give the
        # overall connection at least that long instead of timing out under
        # a real human.
        async with AsyncMCPClient(decrypted.url, auth=job_oauth, timeout=330.0) as client:
            tool_list = await client.list_tools()
            tools = [MCPTestToolInfo(name=t.name, description=t.description) for t in tool_list]

        # Listing tools frequently succeeds without ever exercising
        # credentials -- many MCP servers (Gmail's included) only gate
        # individual tool calls, not `tools/list`. Without forcing a real
        # call, the OAuth challenge (and thus the login prompt) would never
        # fire, and the job would report "succeeded" despite never having
        # obtained a token.
        #
        # This verification call deliberately opens a *second, fresh*
        # connection rather than reusing the one above: streamable-http
        # sessions are sticky (tied to a server-issued session id from
        # `initialize`), so a session established anonymously during
        # tools/list can't be retroactively "upgraded" to authenticated by a
        # 401 challenge on a later call over the same session -- observed
        # against Google's endpoint as the tool call hanging indefinitely
        # even after a real, successful login. A fresh connection means its
        # own `initialize` is what gets challenged, so the whole session is
        # authenticated from the start.
        if tool_call is not None and tool_call.name in [t.name for t in tools]:
            verified = False
            try:
                # This connection may or may not already hold a valid token:
                # for providers that gate individual tool calls rather than
                # `tools/list` (see the comment above -- Gmail included),
                # THIS is the connection whose `initialize` first triggers
                # the 401 challenge, so it can just as well need the human to
                # complete a fresh login/consent screen as the first
                # connection above did. Bound it at the same 330s
                # human-consent budget rather than a short one, which would
                # cut off a real, in-progress login. An already-authenticated
                # retry still completes almost immediately under this bound;
                # it does not have to be tight to keep that case fast.
                async with asyncio.timeout(330.0):
                    async with AsyncMCPClient(decrypted.url, auth=job_oauth, timeout=330.0) as verify_client:
                        # The 401 challenge for a tool-call-gated provider
                        # (Gmail included) fires from *this* call, not from
                        # `verify_client`'s `initialize` above -- so this
                        # inner wait is what actually needs the full
                        # human-consent budget, not just the outer one.
                        await asyncio.wait_for(
                            verify_client.call_tool_mcp(
                                name=tool_call.name, arguments=tool_call.arguments
                            ),
                            timeout=330.0,
                        )
                        verified = True
            except Exception:
                if not verified:
                    raise
                # The call itself already completed inside the block above;
                # this is a teardown-only failure (e.g. a provider rejecting
                # the session-terminate request) and must not fail a job
                # that already has what it needs.
                logger.info(
                    "MCP OAuth job %s: ignoring post-verification teardown error",
                    job_id,
                    exc_info=True,
                )

        # Record success only once the verification call (if any) has
        # actually completed -- a 403/error on session teardown afterward
        # (e.g. a provider rejecting the streamable-http "terminate
        # session" request) must not wipe out a handshake and tool call
        # that both genuinely succeeded moments earlier.
        job.tools = tools
        oauth_state = token_store.export_state()
        tokens_value = oauth_state.get_token_storage_value("tokens")
        if tokens_value is not None:
            # Stamp an absolute wall-clock expiry alongside the relative
            # ``expires_in`` before this state is handed to the frontend and
            # persisted via `/api/settings` -- that path bypasses
            # MCPSettingsOAuthTokenStore.put() entirely, so without this the
            # token would be saved unstamped and look freshly valid forever
            # on reload. See mcp_integration.config.stamp_absolute_token_expiry.
            oauth_state = oauth_state.with_token_storage_value(
                "tokens", stamp_absolute_token_expiry(tokens_value)
            )
        job.oauth_state = oauth_state
        job.status = "succeeded"
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - surfaced to the UI, not swallowed
        # SystemExit (not a normal Exception -- must be listed explicitly)
        # is what uvicorn's Server.startup() raises when it can't bind the
        # shared OAuth callback port. Left uncaught, it propagates out of
        # this background task as an unhandled BaseException, which can take
        # the whole server process down with it instead of just failing this
        # one job -- see _oauth_callback_port and _cancel_oauth_job.
        if job.status == "succeeded":
            # The real work (auth handshake + verification call) already
            # completed inside the `async with` block; this exception is
            # from connection teardown afterward (e.g. a provider rejecting
            # the streamable-http session-terminate request) and must not
            # overwrite a result the caller already has.
            logger.info(
                "MCP OAuth job %s: ignoring post-success teardown error", job_id, exc_info=True
            )
            return
        logger.warning("MCP OAuth job %s failed", job_id, exc_info=True)
        job.status = "failed"
        # httpx.HTTPStatusError's str() is just "403 Forbidden for url ..." --
        # the actual diagnostic (e.g. which API needs enabling) is in the
        # response body, which callers need to fix a real provider-side
        # config issue rather than guess at it.
        detail = str(exc) or type(exc).__name__
        try:
            response = getattr(exc, "response", None)
            # ``.text`` raises ResponseNotRead on an httpx response that was
            # streamed but never explicitly read -- exactly the case for an
            # async client's error responses. Read it defensively; this must
            # never itself raise, or the real error above is lost.
            if response is not None and getattr(response, "is_stream_consumed", True) is False:
                await response.aread()
            body_text = getattr(response, "text", None) if response is not None else None
            if body_text:
                detail = f"{detail}\nResponse body: {body_text[:2000]}"
        except Exception:  # noqa: BLE001 - best-effort enrichment only
            pass
        job.error = detail
        job.error_kind = _classify_oauth_error(exc)
    finally:
        job.updated.set()


class OAuthStartResponse(BaseModel):
    ok: bool = True
    job_id: str | None = None
    authorization_url: str | None = None
    error: str | None = None
    error_kind: OAuthErrorKind | None = None


class OAuthStatusResponse(BaseModel):
    ok: bool = True
    status: OAuthJobStatus
    job_id: str
    authorization_url: str | None = None
    callback_ready: bool = False
    tools: list[MCPTestToolInfo] | None = None
    oauth_state: MCPOAuthStateResponse | None = None
    error: str | None = None
    error_kind: OAuthErrorKind | None = None


@mcp_router.post(
    "/oauth/start",
    response_model=OAuthStartResponse,
    response_model_exclude_none=True,
    summary="Start an MCP OAuth authorization job",
    description=(
        "Begins a browser-based OAuth flow for a candidate MCP server "
        "(auth.strategy='oauth2'). Returns a job id and, once the provider "
        "redirect is known, an authorization_url the caller should open in "
        "the user's browser. Poll GET /oauth/status/{job_id} for completion."
    ),
)
async def start_mcp_oauth(request: MCPTestRequest, http_request: Request) -> OAuthStartResponse:
    await _prune_oauth_jobs()
    cipher = get_cipher(http_request)
    server = request.resolved_server
    if server.oauth_auth is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="server.auth.strategy must be 'oauth2' to start an OAuth job",
        )

    # A duplicate Connect click, a Re-authenticate fired while the first
    # attempt is still pending, or a stale dialog re-submitting -- all just
    # want the *same* authorization to still be in flight, not a fresh one.
    # Reuse the existing job instead of cancelling and rebinding the shared
    # callback port: that path is unreliable (fastmcp's own callback server
    # can take far longer than its own 100ms shutdown grace period to
    # actually release the port -- see _cancel_oauth_job) and was the
    # original source of the SystemExit crash this endpoint now also
    # defends against below.
    for existing_id, existing_job in _OAUTH_JOBS.items():
        if existing_job.server_key == server.url and existing_job.status in (
            "pending",
            "authorizing",
        ):
            return OAuthStartResponse(
                ok=True, job_id=existing_id, authorization_url=existing_job.authorization_url
            )

    # A *different* server's job is still active. We do need the port, but
    # empirically cancelling it and waiting for the release is unreliable --
    # fastmcp's callback server can take far longer than its own 100ms
    # shutdown grace period to actually free the socket when cancelled
    # externally (see _cancel_oauth_job), sometimes not within tens of
    # seconds. Rather than block the caller that long only to often fail
    # anyway, fail fast with an honest, actionable message: attempt the
    # cancellation in the background (best-effort, so the port is more
    # likely free by the time the user retries) and tell the caller
    # immediately instead of making them wait to find out.
    active = next(
        (
            (jid, job)
            for jid, job in _OAUTH_JOBS.items()
            if job.status in ("pending", "authorizing")
        ),
        None,
    )
    if active is not None:
        active_id, active_job = active
        asyncio.create_task(
            _cancel_oauth_job(
                active_id,
                reason="Superseded by a newer OAuth attempt for a different server.",
            )
        )
        return OAuthStartResponse(
            ok=False,
            error=(
                "Another OAuth authorization is already in progress for a "
                f"different server ({active_job.server_key or 'unknown'}). "
                "It's being cancelled now -- wait a few seconds and try "
                "connecting again."
            ),
            error_kind="port_busy",
        )

    # Defense in depth even when there was no active job to preempt: a
    # previous job's own internal 5-minute timeout can fire (or its uvicorn
    # callback server can still be mid-shutdown) without ever going through
    # _cancel_oauth_job. Confirm the port is actually free rather than
    # finding out via a crashed job (see _classify_oauth_error's
    # "port_busy" case).
    if not await _wait_for_port_release(_oauth_callback_port(), timeout=8.0):
        return OAuthStartResponse(
            ok=False,
            error=(
                f"The OAuth callback port ({_oauth_callback_port()}) is still "
                "in use by a previous authorization attempt. Please wait a "
                "moment and try again."
            ),
            error_kind="port_busy",
        )

    job_id = uuid.uuid4().hex
    job = _OAuthJob(server_key=server.url)
    _OAUTH_JOBS[job_id] = job
    _OAUTH_TASKS[job_id] = asyncio.create_task(
        _run_oauth_job(job_id, server, cipher, request.tool_call)
    )

    # Give the job a moment to reach the authorization redirect (or fail fast
    # on a bad config) so the first response can usually include the URL.
    try:
        await asyncio.wait_for(job.updated.wait(), timeout=_OAUTH_START_WAIT_SECONDS)
    except TimeoutError:
        pass

    if job.status == "failed":
        return OAuthStartResponse(ok=False, job_id=job_id, error=job.error, error_kind=job.error_kind)
    return OAuthStartResponse(ok=True, job_id=job_id, authorization_url=job.authorization_url)


@mcp_router.get(
    "/oauth/status/{job_id}",
    response_model=OAuthStatusResponse,
    response_model_exclude_none=True,
    summary="Poll an MCP OAuth authorization job",
)
async def mcp_oauth_status(job_id: str) -> OAuthStatusResponse:
    job = _OAUTH_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown or expired OAuth job")
    return OAuthStatusResponse(
        ok=job.status != "failed",
        status=job.status,
        job_id=job_id,
        authorization_url=job.authorization_url,
        callback_ready=job.callback_ready,
        tools=job.tools,
        # `has_values` is true even with only client_info (e.g. a
        # pre-registered Google client_id/secret) and no tokens -- that is
        # truthy in JS and would be misread by the UI as "session saved".
        # Only report state that actually holds an access token, so a server
        # whose tools/list happens to succeed without ever exercising
        # credentials isn't shown as authenticated when no OAuth handshake
        # (i.e. no real login) ever completed.
        oauth_state=(
            job.oauth_state.to_response()
            if job.oauth_state is not None
            and job.oauth_state.tokens is not None
            and job.oauth_state.tokens.access_token is not None
            else None
        ),
        error=job.error,
        error_kind=job.error_kind,
    )


@mcp_router.post(
    "/oauth/status/{job_id}/cancel",
    response_model=OAuthStatusResponse,
    response_model_exclude_none=True,
    summary="Cancel a pending MCP OAuth authorization job",
    description=(
        "Cancels an in-flight OAuth job (e.g. the user closed the setup "
        "dialog, or gave up on a stuck consent screen) and releases the "
        "shared callback port. Safe to call on an already-finished job."
    ),
)
async def cancel_mcp_oauth(job_id: str) -> OAuthStatusResponse:
    job = _OAUTH_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown or expired OAuth job")
    await _cancel_oauth_job(job_id, reason="Cancelled by the user.")
    return OAuthStatusResponse(
        ok=False,
        status=job.status,
        job_id=job_id,
        error=job.error,
        error_kind=job.error_kind,
    )


@mcp_router.get(
    "/registry/search",
    summary="Search Official MCP Registry",
    description="Query the official MCP registry at registry.modelcontextprotocol.io",
)
async def search_mcp_registry(q: str = "") -> dict[str, Any]:
    url = "https://registry.modelcontextprotocol.io/v0/servers"
    params = {}
    if q:
        params["search"] = q

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error("Failed to query MCP registry: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to query official MCP registry",
        )
