"""Utility functions for MCP integration."""

import asyncio
import concurrent.futures
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

import mcp.types
from mcp.shared.auth import OAuthClientInformationFull
from fastmcp.client.auth import OAuth
from fastmcp.client.logging import LogMessage
from fastmcp.client.messages import MessageHandler
from fastmcp.mcp_config import MCPConfig as FastMCPConfig, RemoteMCPServer
from key_value.aio.protocols import AsyncKeyValue

from runtime.telemetry.logger import get_logger
from mcp_integration.client import MCPClient
from mcp_integration.config import (
    MCPOAuthAuthCredential,
    MCPOAuthAuthentication,
    MCPServer,
    to_fastmcp_mcp_config,
)
from mcp_integration.exceptions import MCPReauthenticationRequiredError, MCPTimeoutError
from mcp_integration.oauth_provider_config import get_oauth_provider_credentials
from mcp_integration.tool import MCPToolDefinition


logger = get_logger(__name__)
LOGGING_LEVEL_MAP = logging.getLevelNamesMapping()

MCPOAuthFactory = Callable[
    [str, MCPServer, MCPOAuthAuthCredential, AsyncKeyValue | None],
    OAuth | None,
]


class RuntimeOnlyOAuth(OAuth):
    """FastMCP OAuth restricted to non-interactive, already-authorized use.

    Everything (loading/refreshing a persisted token, PKCE, DCR against
    providers that support it) is inherited unchanged -- a still-valid
    persisted token continues to authenticate silently exactly as with plain
    ``OAuth``. The only thing overridden is ``redirect_handler``, the one
    hook FastMCP calls when it has decided interactive authorization is
    required (token missing, expired past refresh, or otherwise unusable).
    The default implementation there opens a browser via
    ``webbrowser.open()`` -- correct for the explicit, user-initiated OAuth
    job (see ``runtime.server.mcp_router._JobOAuth``), but never acceptable
    for runtime tool materialization, which can run at arbitrary times
    (conversation startup, a background tool refresh, a "Test connection"
    click) with no user standing by watching for a popup. This class is used
    everywhere ``create_mcp_tools`` builds OAuth from persisted server
    config; interactive authorization has its own, entirely separate code
    path that never goes through here.
    """

    async def redirect_handler(self, authorization_url: str) -> None:  # noqa: ARG002
        raise MCPReauthenticationRequiredError(self.mcp_url)

# Callback invoked when an MCP server signals that its tool list changed.
# Receives the *newly added* tool definitions; removed tools are dropped from
# the owning client's tool list but are not reported here.
ToolsChangedCallback = Callable[[Sequence[MCPToolDefinition]], None]


class MCPToolProvider(Protocol):
    """Runtime-only MCP tool materializer."""

    def create_tools(
        self,
        mcp_config: dict[str, MCPServer],
        timeout: float = 30.0,
        *,
        on_tools_changed: ToolsChangedCallback | None = None,
    ) -> "MCPClient | _MultiServerMCPClient": ...


class DefaultMCPToolProvider:
    """Runtime MCP tool materializer without extra persistence hooks."""

    def create_tools(
        self,
        mcp_config: dict[str, MCPServer],
        timeout: float = 30.0,
        *,
        on_tools_changed: ToolsChangedCallback | None = None,
    ) -> "MCPClient | _MultiServerMCPClient":
        return create_mcp_tools(mcp_config, timeout, on_tools_changed=on_tools_changed)


def _oauth_auth_from_authentication_config(
    authentication: MCPOAuthAuthentication | None,
    *,
    mcp_url: str,
    mcp_oauth_token_storage: AsyncKeyValue | None = None,
    oauth_cls: type[OAuth] = OAuth,
) -> OAuth | None:
    """Build FastMCP OAuth auth from explicit SDK MCP auth metadata.

    ``oauth_cls`` lets callers substitute a subclass with different
    interactive-authorization behavior (see
    ``runtime.server.mcp_oauth_store._RuntimeOnlyOAuth``) while sharing this
    same client-metadata resolution -- the default ``OAuth``'s
    ``redirect_handler`` opens a browser, which is correct for the explicit
    user-driven OAuth job but never for runtime tool materialization.
    """
    if authentication is None:
        return None

    additional_client_metadata = dict(authentication.additional_client_metadata or {})
    client_auth_method = authentication.client_auth_method
    if client_auth_method is not None:
        additional_client_metadata["token_endpoint_auth_method"] = client_auth_method

    # Providers without dynamic client registration (Google, Slack, ...) need
    # a pre-registered client_id/secret -- see mcp_integration.oauth_provider_
    # config, the same backend-only config runtime.server.mcp_router's
    # explicit OAuth job already resolves this from. Without it, a runtime
    # connection (ambient MCP activation, an authenticated tool call, ...)
    # has no client_id to send and the underlying OAuth client falls back to
    # dynamic client registration, which those providers reject outright
    # (Google's endpoint 404s on /register) -- a caller-supplied client_id
    # (legacy/custom servers) still wins if present.
    client_id = authentication.client_id
    client_secret = authentication.client_secret
    if client_id is None and authentication.provider is not None:
        provider_creds = get_oauth_provider_credentials(authentication.provider)
        if provider_creds is not None:
            client_id = provider_creds.client_id
            client_secret = provider_creds.client_secret
        else:
            logger.warning(
                "MCP OAuth provider '%s' has no pre-registered client_id/secret "
                "configured (see mcp_integration/oauth_provider_config.py); "
                "falling back to dynamic client registration, which this "
                "provider likely rejects.",
                authentication.provider,
            )

    if client_id is not None:
        additional_client_metadata["client_id"] = client_id
    if client_secret is not None:
        additional_client_metadata["client_secret"] = client_secret.get_secret_value()

    # We must return an OAuth instance, but mcp_url is required.
    oauth_auth = oauth_cls(
        mcp_url=mcp_url,
        scopes=authentication.scopes,
        client_name=authentication.client_name or "FastMCP Client",
        token_storage=mcp_oauth_token_storage,
        additional_client_metadata=additional_client_metadata or None,
    )

    # `additional_client_metadata["client_id"]` above only shapes the
    # metadata FastMCP would send *during* dynamic client registration --
    # mcp.client.auth.oauth2's async_auth_flow only skips registration when
    # ``self.context.client_info`` is already populated (loaded from
    # ``storage.get_client_info()``), which is empty on a fresh store. For
    # providers without DCR support (Google, Slack, ...) that means every
    # connection still attempts registration and gets rejected (Google's
    # endpoint 404s on /register) even with a resolved client_id. The fix is
    # to pre-seed the token storage with client info directly, exactly as
    # ``runtime.server.mcp_router._run_oauth_job`` already does for the
    # interactive OAuth job. That seeding is async
    # (``TokenStorageAdapter.set_client_info``) and this function is sync, so
    # we stash the desired info here and let the caller (``create_mcp_tools``,
    # which already runs on the client's background event loop) perform the
    # actual write before ``client.connect()`` triggers the OAuth flow.
    if client_id is not None:
        oauth_auth._pending_client_info = OAuthClientInformationFull(  # type: ignore[attr-defined]
            client_id=client_id,
            client_secret=client_secret.get_secret_value() if client_secret else None,
            redirect_uris=[f"http://localhost:{oauth_auth.redirect_port}/callback"],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            # Without this, mcp.client.auth.oauth2's prepare_token_auth only
            # attaches client_secret when token_endpoint_auth_method is
            # explicitly "client_secret_basic" or "client_secret_post" --
            # leaving it unset drops the secret from the token exchange
            # entirely even though we have one.
            token_endpoint_auth_method=(
                "client_secret_post" if client_secret else "none"
            ),
        )

    return oauth_auth


async def _seed_pending_oauth_client_info(config: FastMCPConfig) -> None:
    """Write any pre-registered OAuth client info stashed on this config.

    Must run on the MCP client's own event loop, before ``client.connect()``
    -- see ``_oauth_auth_from_authentication_config`` for why this can't just
    happen at OAuth-object construction time.
    """
    for server in config.mcpServers.values():
        auth = getattr(server, "auth", None)
        pending_client_info = getattr(auth, "_pending_client_info", None)
        if pending_client_info is not None:
            await auth.token_storage_adapter.set_client_info(pending_client_info)


def _prepare_mcp_config(
    mcp_config: dict[str, MCPServer],
    *,
    mcp_oauth_token_storage: AsyncKeyValue | None = None,
    mcp_oauth_factory: MCPOAuthFactory | None = None,
) -> FastMCPConfig:
    """Validate MCP config and apply explicit HRAgents runtime auth metadata."""
    prepared = FastMCPConfig.model_validate(to_fastmcp_mcp_config(mcp_config))

    for server_name, server_spec in mcp_config.items():
        auth = server_spec.auth
        if not isinstance(auth, MCPOAuthAuthCredential):
            continue
        server = prepared.mcpServers.get(server_name)
        if not isinstance(server, RemoteMCPServer) or server.auth != "oauth":
            continue
        # No caller of create_mcp_tools() may build an interactive OAuth
        # client here by default -- RuntimeOnlyOAuth is the fallback
        # whenever mcp_oauth_factory doesn't supply one of its own, so a
        # stale/missing token can never make this call site open a browser.
        # The one legitimate interactive flow (the explicit, user-initiated
        # `/api/mcp/oauth/start` job) never goes through create_mcp_tools --
        # it builds FastMCP's real ``OAuth`` directly. See RuntimeOnlyOAuth's
        # docstring.
        server_url = getattr(server_spec, "url", None) or "http://localhost"
        oauth_auth = (
            mcp_oauth_factory(
                server_name,
                server_spec,
                auth,
                mcp_oauth_token_storage,
            )
            if mcp_oauth_factory is not None
            else _oauth_auth_from_authentication_config(
                auth.authentication,
                mcp_url=server_url,
                mcp_oauth_token_storage=mcp_oauth_token_storage,
                oauth_cls=RuntimeOnlyOAuth,
            )
        )
        if oauth_auth is not None:
            server.auth = oauth_auth
        elif mcp_oauth_token_storage is not None:
            server.auth = RuntimeOnlyOAuth(server_url, token_storage=mcp_oauth_token_storage)

    return prepared


def _require_native_mcp_config(
    mcp_config: Mapping[str, MCPServer],
) -> dict[str, MCPServer]:
    if not isinstance(mcp_config, Mapping):
        raise TypeError(
            "create_mcp_tools expects native MCP servers: dict[str, MCPServer]. "
            "Use coerce_mcp_config() at external config boundaries."
        )

    invalid = [
        name
        for name, server in mcp_config.items()
        if not isinstance(name, str) or not isinstance(server, MCPServer)
    ]
    if invalid:
        raise TypeError(
            "create_mcp_tools expects native MCP servers: dict[str, MCPServer]. "
            "Use coerce_mcp_config() at external config boundaries."
        )
    return dict(mcp_config)


async def log_handler(message: LogMessage):
    """
    Handles incoming logs from the MCP server and forwards them
    to the standard Python logging system.
    """
    msg = message.data.get("msg")
    extra = message.data.get("extra")

    # Convert the MCP log level to a Python log level
    level = LOGGING_LEVEL_MAP.get(message.level.upper(), logging.INFO)

    # Log the message using the standard logging library
    logger.log(level, msg, extra=extra)


async def _connect_and_list_tools(
    client: MCPClient,
    mcp_config: dict[str, MCPServer] | None = None,
    tool_name_prefix: str | None = None,
) -> None:
    """Connect to MCP server and populate client._tools."""
    await client.connect()
    await _refresh_tools(client, mcp_config=mcp_config, tool_name_prefix=tool_name_prefix)


async def _refresh_tools(
    client: MCPClient,
    on_tools_changed: ToolsChangedCallback | None = None,
    mcp_config: dict[str, MCPServer] | None = None,
    tool_name_prefix: str | None = None,
) -> None:
    """Re-list tools from the server and reconcile ``client._tools``.

    Called after the initial connection and whenever the server sends a
    ``notifications/tools/list_changed`` notification. When an
    ``on_tools_changed`` callback is supplied, newly discovered tools are
    reported so a running agent can register them via ``add_runtime_tools``.
    Tools that are no longer advertised are dropped from ``client._tools`` but
    are not proactively removed from an agent's tool map.

    ``tool_name_prefix``, when set, renames each tool's agent-facing name to
    ``{prefix}_{tool_name}`` (matching fastmcp's own multi-server composite
    transport convention) while the RPC call against ``client`` still uses
    the tool's real, unprefixed name -- see ``MCPToolDefinition.create``'s
    ``remote_tool_name``.
    """
    raw_tools: list[mcp.types.Tool] = await client.list_tools()
    if tool_name_prefix:
        listed_tools = [
            (tool, tool.model_copy(update={"name": f"{tool_name_prefix}_{tool.name}"}))
            for tool in raw_tools
        ]
    else:
        listed_tools = [(tool, tool) for tool in raw_tools]

    existing_by_name = {tool.name: tool for tool in client._tools}
    server_names = {display_tool.name for _, display_tool in listed_tools}

    reconciled: list[MCPToolDefinition] = []
    added: list[MCPToolDefinition] = []
    for remote_tool, display_tool in listed_tools:
        prior = existing_by_name.get(display_tool.name)
        if prior is not None:
            # Preserve the existing definition so its executor (and the
            # shared MCPClient it closes on shutdown) stays wired up.
            reconciled.append(prior)
            continue
        # Get tool permission from server config (keyed by the real,
        # unprefixed tool name as configured).
        tool_permission = None
        if mcp_config is not None:
            for server_spec in mcp_config.values():
                if (
                    server_spec.tool_permissions
                    and remote_tool.name in server_spec.tool_permissions
                ):
                    tool_permission = server_spec.tool_permissions[remote_tool.name]
                    break
        tool_sequence = MCPToolDefinition.create(
            mcp_tool=display_tool,
            mcp_client=client,
            tool_permission=tool_permission,
            remote_tool_name=remote_tool.name,
        )
        reconciled.extend(tool_sequence)
        added.extend(tool_sequence)

    # Drop tools the server no longer advertises. Reassign atomically so
    # concurrent readers iterating client.tools never observe mid-update state.
    removed = [
        tool.name for name, tool in existing_by_name.items() if name not in server_names
    ]
    if removed:
        logger.info("MCP server removed tools: %s", ", ".join(sorted(removed)))
    client._tools = reconciled

    if added and on_tools_changed is not None:
        try:
            on_tools_changed(added)
        except Exception:
            logger.warning(
                "on_tools_changed callback failed for %d new MCP tools",
                len(added),
                exc_info=True,
            )


class _ToolListChangedHandler(MessageHandler):
    """Message handler that refreshes tools on ``tools/list_changed``.

    Some MCP servers (e.g. Datadog's hosted server) use progressive
    disclosure: they expose a small gateway toolset at connect time and
    register additional tools only after a skill-loading tool is invoked,
    signalling the change with ``notifications/tools/list_changed``. Without
    subscribing, the client never re-lists and the new tools stay invisible.
    """

    def __init__(
        self,
        client: MCPClient,
        on_tools_changed: ToolsChangedCallback | None = None,
        mcp_config: dict[str, MCPServer] | None = None,
        tool_name_prefix: str | None = None,
    ):
        super().__init__()
        self._client = client
        self._on_tools_changed = on_tools_changed
        self._mcp_config = mcp_config
        self._tool_name_prefix = tool_name_prefix
        self._refresh_lock = asyncio.Lock()
        self._refresh_tasks: set[asyncio.Task[None]] = set()

    async def on_tool_list_changed(
        self,
        message: mcp.types.ToolListChangedNotification,  # noqa: ARG002
    ) -> None:
        client = self._client
        if client._closed:
            return
        logger.debug("MCP tools/list_changed received; refreshing tools")
        # Keep the receive loop free to process the list_tools response.
        task = asyncio.create_task(self._refresh_tools())
        self._refresh_tasks.add(task)
        task.add_done_callback(self._refresh_tasks.discard)

    async def _refresh_tools(self) -> None:
        client = self._client
        try:
            async with self._refresh_lock:
                if client._closed:
                    return
                await _refresh_tools(
                    client,
                    self._on_tools_changed,
                    self._mcp_config,
                    self._tool_name_prefix,
                )
        except Exception:
            logger.warning(
                "Failed to refresh MCP tools after list_changed notification",
                exc_info=True,
            )


class _MultiServerMCPClient:
    """Aggregates tools from independently-connected per-server MCP clients.

    Returned by ``create_mcp_tools`` in place of a single ``MCPClient`` when
    more than one server is configured -- see ``_create_isolated_multi_server_mcp_tools``
    for why. Exposes just the surface callers actually use (``.tools``, and
    context-manager/``sync_close`` teardown); each tool still executes
    against the specific per-server ``MCPClient`` it was created from, so no
    call routing happens here.
    """

    def __init__(
        self, clients: list[MCPClient], tools: list[MCPToolDefinition]
    ) -> None:
        self._clients = clients
        self._tools = tools

    @property
    def tools(self) -> list[MCPToolDefinition]:
        return list(self._tools)

    def sync_close(self) -> None:
        for client in self._clients:
            try:
                client.sync_close()
            except Exception:
                logger.warning(
                    "Failed to close MCP client during cleanup", exc_info=True
                )

    def __enter__(self) -> "_MultiServerMCPClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.sync_close()


def _create_isolated_multi_server_mcp_tools(
    mcp_config: dict[str, MCPServer],
    timeout: float,
    *,
    on_tools_changed: ToolsChangedCallback | None,
    mcp_oauth_token_storage: AsyncKeyValue | None,
    mcp_oauth_factory: MCPOAuthFactory | None,
) -> _MultiServerMCPClient:
    """Connect to each configured MCP server independently, in parallel.

    fastmcp's own multi-server transport mounts every server on one shared
    connection, so a single server hanging on auth (e.g. a stale OAuth token
    triggering a full interactive re-auth flow instead of a refresh) exhausts
    the shared timeout and zeroes out tools for every *other* configured
    server too -- one bad connection takes down the whole conversation.
    Connecting per-server isolates that failure to just the affected server;
    each server still gets its full ``timeout`` budget, but they run
    concurrently so the overall wait is bounded by the slowest one, not the
    sum. Tool names are manually prefixed as ``{server_name}_{tool_name}`` to
    match the naming convention fastmcp's own composite transport would have
    used.
    """
    clients: list[MCPClient] = []
    all_tools: list[MCPToolDefinition] = []

    def _connect_one(server_name: str, server_spec: MCPServer) -> MCPClient:
        result = create_mcp_tools(
            {server_name: server_spec},
            timeout,
            on_tools_changed=on_tools_changed,
            mcp_oauth_token_storage=mcp_oauth_token_storage,
            mcp_oauth_factory=mcp_oauth_factory,
            tool_name_prefix=server_name,
        )
        assert isinstance(result, MCPClient)
        return result

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(mcp_config), thread_name_prefix="mcp-connect"
    ) as pool:
        futures = {
            pool.submit(_connect_one, server_name, server_spec): server_name
            for server_name, server_spec in mcp_config.items()
        }
        for future in concurrent.futures.as_completed(futures):
            server_name = futures[future]
            try:
                client = future.result()
            except Exception as exc:  # noqa: BLE001 - isolate this server's failure only
                logger.warning(
                    "MCP server %r failed to connect; continuing without its "
                    "tools. Use /api/mcp/test for the per-server error: %s",
                    server_name,
                    exc,
                )
                continue
            clients.append(client)
            all_tools.extend(client.tools)

    return _MultiServerMCPClient(clients, all_tools)


def create_mcp_tools(
    mcp_config: dict[str, MCPServer],
    timeout: float = 30.0,
    *,
    on_tools_changed: ToolsChangedCallback | None = None,
    mcp_oauth_token_storage: AsyncKeyValue | None = None,
    mcp_oauth_factory: MCPOAuthFactory | None = None,
    tool_name_prefix: str | None = None,
) -> MCPClient | _MultiServerMCPClient:
    """Create MCP tools from HRAgents-native MCP server settings.

    Returns an MCPClient with tools populated. Use as a context manager:

        with create_mcp_tools(mcp_config) as client:
            for tool in client.tools:
                # use tool
        # Connection automatically closed

    The client subscribes to ``notifications/tools/list_changed`` and
    reconciles its tool list whenever the server signals a change. When
    ``on_tools_changed`` is provided, the client invokes it with newly added
    tool definitions so progressive-disclosure servers can surface them to an
    agent. The callback runs on the client's background event-loop thread, so
    callers must ensure it is thread-safe (e.g. ``Agent.add_runtime_tools``).

    When ``mcp_config`` has more than one server, each is connected to
    independently (see ``_create_isolated_multi_server_mcp_tools``) so one
    server hanging on auth can't block every other server's tools; a
    ``_MultiServerMCPClient`` aggregating their tools is returned instead of
    a single ``MCPClient``.
    """
    mcp_config = _require_native_mcp_config(mcp_config)
    if len(mcp_config) > 1:
        return _create_isolated_multi_server_mcp_tools(
            mcp_config,
            timeout,
            on_tools_changed=on_tools_changed,
            mcp_oauth_token_storage=mcp_oauth_token_storage,
            mcp_oauth_factory=mcp_oauth_factory,
        )

    config = _prepare_mcp_config(
        mcp_config,
        mcp_oauth_token_storage=mcp_oauth_token_storage,
        mcp_oauth_factory=mcp_oauth_factory,
    )
    handler = _ToolListChangedHandler(
        client=None,  # type: ignore[arg-type]
        on_tools_changed=on_tools_changed,
        mcp_config=mcp_config,
        tool_name_prefix=tool_name_prefix,
    )
    client = MCPClient(config, log_handler=log_handler, message_handler=handler)
    handler._client = client

    try:
        client.call_async_from_sync(
            _seed_pending_oauth_client_info,
            timeout=timeout,
            config=config,
        )
        client.call_async_from_sync(
            _connect_and_list_tools,
            timeout=timeout,
            client=client,
            mcp_config=mcp_config,
            tool_name_prefix=tool_name_prefix,
        )
    except TimeoutError as e:
        client.sync_close()
        # Extract server names from config for better error message
        server_names = (
            list(config.mcpServers.keys()) if config.mcpServers else ["unknown"]
        )
        error_msg = (
            f"MCP tool listing timed out after {timeout} seconds.\n"
            f"MCP servers configured: {', '.join(server_names)}\n\n"
            "Possible solutions:\n"
            "  1. Increase the timeout value (default is 30 seconds)\n"
            "  2. Check if the MCP server is running and responding\n"
            "  3. Verify network connectivity to the MCP server\n"
        )
        raise MCPTimeoutError(
            error_msg, timeout=timeout, config=config.model_dump()
        ) from e
    except BaseException:
        try:
            client.sync_close()
        except Exception as close_exc:
            logger.warning(
                "Failed to close MCP client during error cleanup", exc_info=close_exc
            )
        raise

    logger.info("Created %d MCP tools", len(client.tools))
    return client
