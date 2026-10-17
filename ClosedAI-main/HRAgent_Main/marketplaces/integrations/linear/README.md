# Linear Integration

Official Linear MCP server integration for HRAgent.

## Server

- **Transport**: SSE (Server-Sent Events)
- **URL**: `https://mcp.linear.app/mcp`
- **Authentication**: OAuth 2.0

## Tools

| Tool | Description |
|------|-------------|
| `linear_create_issue` | Create a new issue |
| `linear_get_issues` | List issues |
| `linear_get_issue` | Get issue details |
| `linear_update_issue` | Update an existing issue |
| `linear_search_issues` | Search issues |

## Setup

1. Go to [Linear Developer Settings](https://linear.app/settings/api)
2. Create a new OAuth application
3. Add redirect URI: `http://localhost:8000/api/mcp/oauth/callback` (or your backend URL)
4. Add the client ID and secret as settings secrets:
   - `LINEAR_CLIENT_ID`
   - `LINEAR_CLIENT_SECRET`
5. Install this integration from the Marketplace
6. Configure the integration and start OAuth flow

## Scopes Required

- `read` - Read access to issues, projects, teams
- `write` - Write access to create/update issues
- `admin` - Admin access (if needed)

## Notes

This uses the official Linear-hosted MCP endpoint with SSE transport and OAuth 2.0 authentication. The server handles token persistence automatically.

**Note:** The SSE endpoint at `https://mcp.linear.app/mcp` requires valid OAuth authentication for the probe to succeed — unauthenticated probes time out.