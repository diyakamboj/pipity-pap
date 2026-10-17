"""MCP (Model Context Protocol) integration for agent-sdk."""

from typing import TYPE_CHECKING

from mcp_integration.client import MCPClient
from mcp_integration.config import (
    MCPAuthCredential,
    MCPOAuthAuthCredential,
    MCPOAuthAuthentication,
    MCPOAuthState,
    MCPOAuthStateResponse,
    MCPServer,
    to_fastmcp_mcp_config,
)
from mcp_integration.exceptions import MCPError, MCPTimeoutError


if TYPE_CHECKING:
    from mcp_integration.definition import MCPToolAction, MCPToolObservation
    from mcp_integration.tool import MCPToolDefinition, MCPToolExecutor
    from mcp_integration.utils import MCPToolProvider, create_mcp_tools


def __getattr__(name: str):
    if name in {"MCPToolAction", "MCPToolObservation"}:
        from mcp_integration import definition

        value = getattr(definition, name)
    elif name in {"MCPToolDefinition", "MCPToolExecutor"}:
        from mcp_integration import tool

        value = getattr(tool, name)
    elif name in {"MCPToolProvider", "create_mcp_tools"}:
        from mcp_integration import utils

        value = getattr(utils, name)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


__all__ = [
    "MCPClient",
    "MCPAuthCredential",
    "MCPOAuthAuthCredential",
    "MCPOAuthAuthentication",
    "MCPOAuthState",
    "MCPOAuthStateResponse",
    "MCPServer",
    "MCPToolDefinition",
    "MCPToolAction",
    "MCPToolObservation",
    "MCPToolExecutor",
    "MCPToolProvider",
    "create_mcp_tools",
    "to_fastmcp_mcp_config",
    "MCPError",
    "MCPTimeoutError",
]
