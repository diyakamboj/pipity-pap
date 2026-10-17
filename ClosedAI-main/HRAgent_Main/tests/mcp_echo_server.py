"""Tiny FastMCP stdio server exposing one echo tool for end-to-end MCP tests."""
from fastmcp import FastMCP

mcp = FastMCP("e2e-echo-server")


@mcp.tool()
def mcp_echo(text: str) -> str:
    """Echo text back prefixed with mcp:."""
    return f"mcp:{text}"


@mcp.tool()
def mcp_add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


if __name__ == "__main__":
    mcp.run(transport="stdio")