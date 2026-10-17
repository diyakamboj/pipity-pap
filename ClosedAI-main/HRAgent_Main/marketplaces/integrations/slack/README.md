# Slack Integration

Official Slack MCP server integration for HRAgent.

## Server

- **Transport**: Streamable HTTP
- **URL**: `https://mcp.slack.com/mcp`
- **Authentication**: OAuth 2.1 (Slack App)

## Tools

| Tool | Description |
|------|-------------|
| `send_message` | Send a message to a channel |
| `get_channel_history` | Get channel message history |
| `list_channels` | List channels |
| `get_users` | List users |
| `search_messages` | Search messages |
| `create_channel` | Create a new channel |
| `get_channel_members` | Get channel members |

## Setup

1. Go to [Slack API](https://api.slack.com/apps)
2. Create a new Slack App (From manifest or scratch)
3. Configure OAuth & Permissions with required scopes:
   - `channels:read`, `channels:write`, `channels:history`
   - `chat:write`, `groups:read`, `groups:write`, `groups:history`
   - `users:read`, `users:read.email`
   - `im:read`, `im:write`, `im:history`
   - `mpim:read`, `mpim:write`, `mpim:history`
4. Install the app to your workspace
5. Add the client ID and secret as settings secrets:
   - `SLACK_CLIENT_ID`
   - `SLACK_CLIENT_SECRET`
6. Install this integration from the Marketplace
7. Configure the integration and start OAuth flow

## Scopes Required

The official Slack MCP server handles OAuth 2.1 with PKCE. Required scopes are automatically requested during the OAuth flow.

## Notes

This uses the official Slack-hosted MCP endpoint (https://mcp.slack.com/mcp) with Streamable HTTP transport and OAuth 2.1 authentication. The server handles token persistence automatically.