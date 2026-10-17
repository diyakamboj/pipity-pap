# Google People Integration

Official Google People MCP server integration for HRAgent.

## Server

- **Transport**: Streamable HTTP
- **URL**: `https://people.googleapis.com/mcp/v1`
- **Authentication**: OAuth 2.0 (Google)

## Tools

| Tool | Description |
|------|-------------|
| `search_directory_people` | Search the domain directory for people |
| `search_contacts` | Search user's contacts |
| `get_user_profile` | Get user profile |

## Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project
3. Enable the **Google People API**
4. Configure OAuth consent screen (External, add test users)
5. Create OAuth 2.0 Client ID (Desktop application)
6. Add the client ID and secret as settings secrets:
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`
7. Install this integration from the Marketplace
8. Configure the integration and start OAuth flow

## Scopes Required

- `https://www.googleapis.com/auth/contacts`
- `https://www.googleapis.com/auth/contacts.readonly`
- `https://www.googleapis.com/auth/directory.readonly`

## Notes

This uses the official Google-hosted MCP endpoint. The server handles OAuth token persistence automatically (disk-backed encrypted cache).