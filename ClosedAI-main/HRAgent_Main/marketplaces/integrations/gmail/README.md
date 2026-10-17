# Gmail Integration (pilot)

Gmail via the official Google MCP server (`https://gmailmcp.googleapis.com/mcp/v1`).
Named pilot: the guided Google-OAuth provisioning step lives in
`marketplaces/VERIFY.md` and the implementation plan.

| | |
|---|---|
| Category | Communication |
| Authentication | Google OAuth 2.0 |
| Server | Official Google Workspace MCP (hosted) |
| Transport | streamable-http (remote) |
| Status | not installed |

## Install

Install from the marketplace (attaches a server named `gmail`) via
`POST /api/plugins/install` with `source = <resolved ./marketplaces/integrations/gmail path>`.

## Authentication (Google OAuth)

The server uses Google's OAuth auto-auth flow:

1. Create a GCP project, enable the **Gmail API**, configure the OAuth consent
   screen, and create an OAuth client ID (Desktop app) → client id + secret.
2. Store the client id/secret as secrets and run the existing
   browser-coordinated OAuth flow (`POST /api/mcp/oauth/start`), which stores
   tokens in the MCP settings OAuth store — no new OAuth code.

## Verify

- **Discovery:** probe the server with no credentials → tools list must load
  (proves install + discovery end-to-end).
- **No-credential error:** a tool call without credentials must return a clean,
  surfaced error (no crash) — a Phase 6 acceptance check.
- **Authenticated execution:** after OAuth completes, `create_draft` /
  `search_threads` execute against the real account.

## Notes

- This uses the official Google-hosted MCP endpoint (not the archived community server).
- Remote transport keeps runtime dependency to zero (no local server needed).
- OAuth token persistence is handled by the remote server (disk-backed encrypted cache).