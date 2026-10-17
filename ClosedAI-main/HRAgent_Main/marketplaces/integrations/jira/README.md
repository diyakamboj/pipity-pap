# Jira Integration

Official Atlassian Jira MCP server integration for HRAgent.

## Server

- **Transport**: Streamable HTTP
- **URL**: `https://mcp.atlassian.com/v1/mcp/authv2`
- **Authentication**: OAuth 2.0 / API Token

## Tools

| Tool | Description |
|------|-------------|
| `getTeamworkGraphContext` | Get teamwork graph context |
| `getTeamworkGraphObject` | Get teamwork graph object |
| `addTeamworkGraphContext` | Add teamwork graph context |

## Setup

### Option 1: OAuth 2.0 (Recommended)

1. Go to [Atlassian Developer Console](https://developer.atlassian.com/console)
2. Create or select an app
3. Enable OAuth 2.0 (3LO) with scopes:
   - `read:jira-work`, `write:jira-work`
   - `read:jira-user`, `write:jira-user`
   - `manage:jira-configuration`
4. Add the client ID and secret as settings secrets:
   - `ATLASSIAN_CLIENT_ID`
   - `ATLASSIAN_CLIENT_SECRET`
5. Install this integration from the Marketplace
6. Configure the integration and start OAuth flow

### Option 2: API Token

1. Create an Atlassian API token at https://id.atlassian.com/manage-profile/security/api-tokens
2. Add as settings secrets:
   - `JIRA_URL` — e.g., `https://your-org.atlassian.net`
   - `JIRA_USERNAME` — your Atlassian email
   - `JIRA_API_TOKEN` — the API token

## Scopes Required (OAuth)

- `read:jira-work`
- `write:jira-work`
- `read:jira-user`
- `offline_access`

## Notes

This uses the official Atlassian-hosted MCP endpoint with Streamable HTTP transport. The server supports both OAuth 2.0 and API token authentication.

**Note:** The official Atlassian MCP server exposes the Teamwork Graph API (getTeamworkGraphContext, getTeamworkGraphObject, addTeamworkGraphContext), not traditional Jira issue operations (jira_get_issue, jira_search_issues, etc.). This is the current state of the official endpoint.