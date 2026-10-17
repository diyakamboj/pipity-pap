# GitHub integration

Official GitHub MCP server, hosted remote (`https://api.githubcopilot.com/mcp/`).
Zero local runtime to install — only a bearer token is required.

| | |
|---|---|
| Category | Development |
| Authentication | Personal Access Token (PAT) |
| Server | `github/github-mcp-server` (official) |
| Transport | streamable-http (remote) |
| Status | not installed |

## Install

Install from the marketplace (attaches a server named `github`) via
`POST /api/plugins/install` with `source = <resolved ./marketplaces/integrations/github path>`.

## Credentials

Set a secret named **`GITHUB_PERSONAL_ACCESS_TOKEN`** (classic PAT with `repo`
and `read:org` scopes, or a fine-grained PAT) via `PUT /api/settings/secrets`.
The `.mcp.json` `Authorization` header resolves `${GITHUB_PERSONAL_ACCESS_TOKEN}`
at conversation build.

## Verify

- Phase 5 repo check: `github/github-mcp-server` — official, active.
- Probe: `POST /api/mcp/test` with the `github` server spec → expect tools list.
- Auth check: `search_code` on a public repo returns results.

## Notes

- Remote transport keeps runtime dependency to zero (no Docker/npx needed).
- Fallback stdio variant (Docker `ghcr.io/github/github-mcp-server`) is
  documented in the implementation plan should the hosted remote be unavailable.
