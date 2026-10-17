# Google Drive Integration

Official Google Drive MCP server integration for HRAgent.

## Server

- **Transport**: Streamable HTTP
- **URL**: `https://drivemcp.googleapis.com/mcp/v1`
- **Authentication**: OAuth 2.0 (Google)

## Tools

| Tool | Description |
|------|-------------|
| `copy_file` | Copy a file |
| `create_file` | Create a new file |
| `download_file_content` | Download file content |
| `get_file_metadata` | Get file metadata |
| `get_file_permissions` | Get file permissions |
| `list_recent_files` | List recent files |
| `read_file_content` | Read file content |
| `search_files` | Search for files |

## Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project
3. Enable the **Google Drive API**
4. Configure OAuth consent screen (External, add test users)
5. Create OAuth 2.0 Client ID (Desktop application)
6. Add the client ID and secret as settings secrets:
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`
7. Install this integration from the Marketplace
8. Configure the integration and start OAuth flow

## Scopes Required

- `https://www.googleapis.com/auth/drive`
- `https://www.googleapis.com/auth/drive.file`
- `https://www.googleapis.com/auth/drive.readonly`

## Notes

This uses the official Google-hosted MCP endpoint. The server handles OAuth token persistence automatically (disk-backed encrypted cache).