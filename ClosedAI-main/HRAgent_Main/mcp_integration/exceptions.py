"""MCP-related exceptions for HRAgents SDK."""


class MCPError(Exception):
    """Base exception for MCP-related errors."""

    pass


class MCPTimeoutError(MCPError):
    """Exception raised when MCP operations timeout."""

    timeout: float
    config: dict | None

    def __init__(self, message: str, timeout: float, config: dict | None = None):
        self.timeout = timeout
        self.config = config
        super().__init__(message)


class MCPReauthenticationRequiredError(MCPError):
    """Raised instead of launching interactive OAuth during runtime.

    A configured OAuth2 MCP server's persisted credentials are missing,
    expired, or otherwise unusable without a fresh interactive authorization
    step. Runtime conversation startup must never perform that step itself
    (it would mean the backend server process opening a browser); only the
    explicit ``POST /api/mcp/oauth/start`` job -- driven by the user clicking
    Connect/Reconnect in the UI -- is allowed to. See
    ``runtime.server.mcp_oauth_store._RuntimeOnlyOAuth``, whose
    ``redirect_handler`` raises this instead of the interactive default.
    """

    server_name: str

    def __init__(self, server_name: str):
        self.server_name = server_name
        super().__init__(
            f"MCP server {server_name!r} needs re-authentication -- its "
            "persisted OAuth session is missing, expired, or invalid. "
            "Reconnect it from MCP Settings."
        )
