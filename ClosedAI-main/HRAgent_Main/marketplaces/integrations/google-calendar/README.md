# Google Calendar Integration

Official Google Calendar MCP server integration for HRAgent.

## Server

- **Transport**: Streamable HTTP
- **URL**: `https://calendarmcp.googleapis.com/mcp/v1`
- **Authentication**: OAuth 2.0 (Google)

## Tools

| Tool | Description |
|------|-------------|
| `list_events` | List events from a calendar |
| `get_event` | Get event details |
| `list_calendars` | List all calendars |
| `suggest_time` | Suggest available time slots |
| `create_event` | Create a new calendar event |
| `update_event` | Update an existing calendar event |
| `delete_event` | Delete a calendar event |
| `respond_to_event` | Respond to a calendar event |
| `search_events` | Search for events |

## Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project
3. Enable the **Google Calendar API**
4. Configure OAuth consent screen (External, add test users)
5. Create OAuth 2.0 Client ID (Desktop application)
6. Add the client ID and secret as settings secrets:
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`
7. Install this integration from the Marketplace
8. Configure the integration and start OAuth flow

## Scopes Required

- `https://www.googleapis.com/auth/calendar`
- `https://www.googleapis.com/auth/calendar.readonly`

## Notes

This uses the official Google-hosted MCP endpoint. The server handles OAuth token persistence automatically (disk-backed encrypted cache).